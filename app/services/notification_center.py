from __future__ import annotations

import sqlite3
import time
import urllib.error
import urllib.request
from contextlib import closing
from json import dumps as json_dumps
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.time import utc_now

class NotificationCenter:
    def __init__(
        self,
        db_path: str = "app/data/runtime_notifications.db",
        *,
        webhook_timeout_seconds: float = 3.0,
        webhook_max_attempts: int = 3,
        webhook_backoff_seconds: float = 0.25,
    ) -> None:
        self.db_path = Path(db_path)
        self.webhook_timeout_seconds = max(0.1, float(webhook_timeout_seconds))
        self.webhook_max_attempts = max(1, int(webhook_max_attempts))
        self.webhook_backoff_seconds = max(0.0, float(webhook_backoff_seconds))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    symbol TEXT,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    score REAL,
                    threshold REAL,
                    acknowledged INTEGER NOT NULL DEFAULT 0,
                    snoozed_until TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS channel_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    in_app_enabled INTEGER NOT NULL DEFAULT 1,
                    webhook_enabled INTEGER NOT NULL DEFAULT 0,
                    webhook_url TEXT NOT NULL DEFAULT '',
                    email_enabled INTEGER NOT NULL DEFAULT 0,
                    email_to TEXT NOT NULL DEFAULT '',
                    throttle_window_minutes INTEGER NOT NULL DEFAULT 10,
                    max_notifications_per_window INTEGER NOT NULL DEFAULT 3,
                    quiet_hours_enabled INTEGER NOT NULL DEFAULT 0,
                    quiet_hours_start TEXT NOT NULL DEFAULT '22:00',
                    quiet_hours_end TEXT NOT NULL DEFAULT '07:00',
                    dedupe_window_minutes INTEGER NOT NULL DEFAULT 20
                )
                """
            )
            self._ensure_channel_setting_columns(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dispatch_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    notification_id INTEGER NOT NULL,
                    channel TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    ts TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO channel_settings (id, in_app_enabled, webhook_enabled, webhook_url, email_enabled, email_to)
                VALUES (1, 1, 0, '', 0, '')
                """
            )
            conn.commit()

    def _ensure_channel_setting_columns(self, conn: sqlite3.Connection) -> None:
        columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info(channel_settings)").fetchall()}
        if "throttle_window_minutes" not in columns:
            conn.execute("ALTER TABLE channel_settings ADD COLUMN throttle_window_minutes INTEGER NOT NULL DEFAULT 10")
        if "max_notifications_per_window" not in columns:
            conn.execute("ALTER TABLE channel_settings ADD COLUMN max_notifications_per_window INTEGER NOT NULL DEFAULT 3")
        if "quiet_hours_enabled" not in columns:
            conn.execute("ALTER TABLE channel_settings ADD COLUMN quiet_hours_enabled INTEGER NOT NULL DEFAULT 0")
        if "quiet_hours_start" not in columns:
            conn.execute("ALTER TABLE channel_settings ADD COLUMN quiet_hours_start TEXT NOT NULL DEFAULT '22:00'")
        if "quiet_hours_end" not in columns:
            conn.execute("ALTER TABLE channel_settings ADD COLUMN quiet_hours_end TEXT NOT NULL DEFAULT '07:00'")
        if "dedupe_window_minutes" not in columns:
            conn.execute("ALTER TABLE channel_settings ADD COLUMN dedupe_window_minutes INTEGER NOT NULL DEFAULT 20")

    def channels(self) -> dict[str, Any]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM channel_settings WHERE id = 1").fetchone()
        if row is None:
            return {
                "in_app_enabled": True,
                "webhook_enabled": False,
                "webhook_url": "",
                "email_enabled": False,
                "email_to": "",
                "throttle_window_minutes": 10,
                "max_notifications_per_window": 3,
                "quiet_hours_enabled": False,
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "07:00",
                "dedupe_window_minutes": 20,
            }
        return {
            "in_app_enabled": bool(row["in_app_enabled"]),
            "webhook_enabled": bool(row["webhook_enabled"]),
            "webhook_url": str(row["webhook_url"] or ""),
            "email_enabled": bool(row["email_enabled"]),
            "email_to": str(row["email_to"] or ""),
            "throttle_window_minutes": int(row["throttle_window_minutes"] or 10),
            "max_notifications_per_window": int(row["max_notifications_per_window"] or 3),
            "quiet_hours_enabled": bool(row["quiet_hours_enabled"]),
            "quiet_hours_start": str(row["quiet_hours_start"] or "22:00"),
            "quiet_hours_end": str(row["quiet_hours_end"] or "07:00"),
            "dedupe_window_minutes": int(row["dedupe_window_minutes"] or 20),
        }

    def update_channels(
        self,
        *,
        in_app_enabled: bool,
        webhook_enabled: bool,
        webhook_url: str,
        email_enabled: bool,
        email_to: str,
        throttle_window_minutes: int,
        max_notifications_per_window: int,
        quiet_hours_enabled: bool,
        quiet_hours_start: str,
        quiet_hours_end: str,
        dedupe_window_minutes: int,
    ) -> dict[str, Any]:
        quiet_start = self._normalize_hhmm(quiet_hours_start)
        quiet_end = self._normalize_hhmm(quiet_hours_end)
        with closing(self._connect()) as conn:
            conn.execute(
                """
                UPDATE channel_settings
                SET in_app_enabled = ?, webhook_enabled = ?, webhook_url = ?, email_enabled = ?, email_to = ?,
                    throttle_window_minutes = ?, max_notifications_per_window = ?, quiet_hours_enabled = ?,
                    quiet_hours_start = ?, quiet_hours_end = ?, dedupe_window_minutes = ?
                WHERE id = 1
                """,
                (
                    1 if in_app_enabled else 0,
                    1 if webhook_enabled else 0,
                    webhook_url,
                    1 if email_enabled else 0,
                    email_to,
                    max(1, throttle_window_minutes),
                    max(1, max_notifications_per_window),
                    1 if quiet_hours_enabled else 0,
                    quiet_start,
                    quiet_end,
                    max(1, dedupe_window_minutes),
                ),
            )
            conn.commit()
        return self.channels()

    def create_hot_opportunity(
        self,
        *,
        symbol: str,
        score: float,
        threshold: float,
        thesis: str,
        ts: datetime,
    ) -> dict[str, Any]:
        title = f"Hot opportunity: {symbol}"
        body = f"Score {score:.2f} crossed threshold {threshold:.2f}. {thesis}"
        with closing(self._connect()) as conn:
            settings = self.channels()
            if settings["quiet_hours_enabled"] and self._is_quiet_hours_active(
                ts,
                settings["quiet_hours_start"],
                settings["quiet_hours_end"],
            ):
                self._log_dispatch(
                    conn,
                    notification_id=0,
                    channel="system",
                    status="suppressed_quiet_hours",
                    detail=f"Suppressed during quiet hours {settings['quiet_hours_start']}-{settings['quiet_hours_end']} (UTC).",
                    ts=ts,
                )
                conn.commit()
                return {}
            if self._is_rate_limited(
                conn,
                now=ts,
                window_minutes=int(settings["throttle_window_minutes"]),
                max_notifications=int(settings["max_notifications_per_window"]),
            ):
                self._log_dispatch(
                    conn,
                    notification_id=0,
                    channel="system",
                    status="suppressed_throttle",
                    detail=(
                        "Suppressed by throttle: "
                        f"{settings['max_notifications_per_window']} per {settings['throttle_window_minutes']}m window."
                    ),
                    ts=ts,
                )
                conn.commit()
                return {}
            if self._is_duplicate_symbol_alert(
                conn,
                symbol=symbol,
                now=ts,
                dedupe_window_minutes=int(settings["dedupe_window_minutes"]),
            ):
                self._log_dispatch(
                    conn,
                    notification_id=0,
                    channel="system",
                    status="suppressed_dedupe",
                    detail=(
                        f"Suppressed duplicate symbol alert for {symbol} "
                        f"within {settings['dedupe_window_minutes']}m window."
                    ),
                    ts=ts,
                )
                conn.commit()
                return {}
            cur = conn.execute(
                """
                INSERT INTO notifications (created_at, kind, symbol, title, body, score, threshold, acknowledged, snoozed_until)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL)
                """,
                (ts.isoformat(), "hot_opportunity", symbol, title, body, float(score), float(threshold)),
            )
            notif_id = int(cur.lastrowid or 0)
            notification = self.get_notification(self._public_id(notif_id)) or {}
            self._dispatch_external_channels(conn, notification=notification, settings=settings, ts=ts)
            conn.commit()
        return self.get_notification(self._public_id(notif_id)) or {}

    def create_test_alert(self, *, message: str, ts: datetime) -> dict[str, Any]:
        clean_message = str(message or "").strip() or "Notification channel test from FayeTrader."
        with closing(self._connect()) as conn:
            cur = conn.execute(
                """
                INSERT INTO notifications (created_at, kind, symbol, title, body, score, threshold, acknowledged, snoozed_until)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL)
                """,
                (ts.isoformat(), "test_alert", "", "Notification test alert", clean_message, 0.0, 0.0),
            )
            notif_id = int(cur.lastrowid or 0)
            settings = self.channels()
            notification = self.get_notification(self._public_id(notif_id)) or {}
            self._dispatch_external_channels(conn, notification=notification, settings=settings, ts=ts)
            conn.commit()
        return self.get_notification(self._public_id(notif_id)) or {}

    def list_notifications(self, limit: int = 50, include_acknowledged: bool = False) -> list[dict[str, Any]]:
        now_iso = utc_now().isoformat()
        where_parts: list[str] = []
        params: list[Any] = []
        if not include_acknowledged:
            where_parts.append("acknowledged = 0")
        where_parts.append("(snoozed_until IS NULL OR snoozed_until <= ?)")
        params.append(now_iso)
        where = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        query = f"""
            SELECT *
            FROM notifications
            {where}
            ORDER BY id DESC
            LIMIT ?
        """
        params.append(limit)
        with closing(self._connect()) as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_notification(row) for row in rows]

    def get_notification(self, notification_id: str) -> dict[str, Any] | None:
        parsed = self._parse_id(notification_id)
        if parsed is None:
            return None
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM notifications WHERE id = ?", (parsed,)).fetchone()
        return self._row_to_notification(row) if row else None

    def acknowledge(self, notification_id: str) -> dict[str, Any] | None:
        parsed = self._parse_id(notification_id)
        if parsed is None:
            return None
        with closing(self._connect()) as conn:
            conn.execute("UPDATE notifications SET acknowledged = 1 WHERE id = ?", (parsed,))
            conn.commit()
        return self.get_notification(notification_id)

    def snooze(self, notification_id: str, minutes: int) -> dict[str, Any] | None:
        parsed = self._parse_id(notification_id)
        if parsed is None:
            return None
        until = (utc_now() + timedelta(minutes=max(1, minutes))).isoformat()
        with closing(self._connect()) as conn:
            conn.execute("UPDATE notifications SET snoozed_until = ? WHERE id = ?", (until, parsed))
            conn.commit()
        return self.get_notification(notification_id)

    def recent_dispatches(self, limit: int = 50) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT notification_id, channel, status, detail, ts
                FROM dispatch_log
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "notification_id": self._public_id(int(row["notification_id"])),
                "channel": str(row["channel"]),
                "status": str(row["status"]),
                "detail": str(row["detail"]),
                "ts": str(row["ts"]),
            }
            for row in rows
        ]

    def metrics(self, window_hours: int = 24) -> dict[str, Any]:
        hours = max(1, int(window_hours))
        cutoff = (utc_now() - timedelta(hours=hours)).isoformat()
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT status, COUNT(*) AS cnt
                FROM dispatch_log
                WHERE ts >= ?
                GROUP BY status
                """,
                (cutoff,),
            ).fetchall()
        by_status = {str(row["status"]): int(row["cnt"] or 0) for row in rows}
        return {
            "window_hours": hours,
            "dispatch_counts": by_status,
            "suppressed_total": sum(count for status, count in by_status.items() if status.startswith("suppressed_")),
            "webhook_delivered": int(by_status.get("delivered", 0)),
            "webhook_failed": int(by_status.get("failed", 0)),
        }

    def _row_to_notification(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "notification_id": self._public_id(int(row["id"])),
            "created_at": str(row["created_at"]),
            "kind": str(row["kind"]),
            "symbol": str(row["symbol"] or ""),
            "title": str(row["title"]),
            "body": str(row["body"]),
            "score": float(row["score"] or 0),
            "threshold": float(row["threshold"] or 0),
            "acknowledged": bool(row["acknowledged"]),
            "snoozed_until": str(row["snoozed_until"] or ""),
        }

    def _public_id(self, db_id: int) -> str:
        return f"notif-{db_id:06d}"

    def _parse_id(self, notification_id: str) -> int | None:
        if not notification_id.startswith("notif-"):
            return None
        try:
            return int(notification_id.split("-", maxsplit=1)[1])
        except ValueError:
            return None

    def _normalize_hhmm(self, raw: str) -> str:
        token = str(raw or "").strip()
        parts = token.split(":")
        if len(parts) != 2:
            return "22:00"
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError:
            return "22:00"
        hour = min(23, max(0, hour))
        minute = min(59, max(0, minute))
        return f"{hour:02d}:{minute:02d}"

    def _is_quiet_hours_active(self, ts: datetime, start_hhmm: str, end_hhmm: str) -> bool:
        start = self._minutes_of_day(start_hhmm)
        end = self._minutes_of_day(end_hhmm)
        current = ts.hour * 60 + ts.minute
        if start == end:
            return True
        if start < end:
            return start <= current < end
        return current >= start or current < end

    def _minutes_of_day(self, hhmm: str) -> int:
        normalized = self._normalize_hhmm(hhmm)
        hour, minute = normalized.split(":")
        return int(hour) * 60 + int(minute)

    def _is_rate_limited(self, conn: sqlite3.Connection, *, now: datetime, window_minutes: int, max_notifications: int) -> bool:
        cutoff = (now - timedelta(minutes=max(1, window_minutes))).isoformat()
        row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM notifications
            WHERE kind = 'hot_opportunity' AND created_at >= ?
            """,
            (cutoff,),
        ).fetchone()
        count = int((row["cnt"] if row else 0) or 0)
        return count >= max(1, max_notifications)

    def _is_duplicate_symbol_alert(
        self,
        conn: sqlite3.Connection,
        *,
        symbol: str,
        now: datetime,
        dedupe_window_minutes: int,
    ) -> bool:
        cutoff = (now - timedelta(minutes=max(1, dedupe_window_minutes))).isoformat()
        row = conn.execute(
            """
            SELECT id
            FROM notifications
            WHERE kind = 'hot_opportunity'
              AND symbol = ?
              AND created_at >= ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (symbol, cutoff),
        ).fetchone()
        return row is not None

    def _dispatch_external_channels(
        self,
        conn: sqlite3.Connection,
        *,
        notification: dict[str, Any],
        settings: dict[str, Any],
        ts: datetime,
    ) -> None:
        notif_id = self._parse_id(str(notification.get("notification_id", ""))) or 0
        if settings["webhook_enabled"]:
            webhook_url = str(settings["webhook_url"] or "").strip()
            if not webhook_url:
                self._log_dispatch(
                    conn,
                    notification_id=notif_id,
                    channel="webhook",
                    status="skipped_missing_webhook_url",
                    detail="No webhook_url configured.",
                    ts=ts,
                )
            else:
                status, detail = self._send_webhook_with_retries(webhook_url=webhook_url, notification=notification)
                self._log_dispatch(
                    conn,
                    notification_id=notif_id,
                    channel="webhook",
                    status=status,
                    detail=detail,
                    ts=ts,
                )
        if settings["email_enabled"]:
            email_to = str(settings["email_to"] or "").strip()
            status = "queued_scaffold" if email_to else "skipped_missing_email"
            detail = email_to if email_to else "No email_to configured."
            self._log_dispatch(
                conn,
                notification_id=notif_id,
                channel="email",
                status=status,
                detail=detail,
                ts=ts,
            )

    def _send_webhook_with_retries(self, *, webhook_url: str, notification: dict[str, Any]) -> tuple[str, str]:
        attempt = 0
        last_error = "unknown webhook error"
        while attempt < self.webhook_max_attempts:
            attempt += 1
            try:
                code, response_body = self._post_webhook(webhook_url, notification)
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                if 200 <= code < 300:
                    return "delivered", f"attempt={attempt} http={code} body={response_body[:160]}"
                last_error = f"http={code} body={response_body[:160]}"
            if attempt < self.webhook_max_attempts and self.webhook_backoff_seconds > 0:
                time.sleep(self.webhook_backoff_seconds * attempt)
        return "failed", f"attempts={self.webhook_max_attempts} error={last_error}"

    def _post_webhook(self, webhook_url: str, notification: dict[str, Any]) -> tuple[int, str]:
        payload = {
            "source": "fayetrader",
            "notification": notification,
        }
        body = json_dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url=webhook_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.webhook_timeout_seconds) as response:  # noqa: S310
                code = int(getattr(response, "status", 200))
                raw = response.read(160)
                return code, raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read(160).decode("utf-8", errors="replace")
            return int(exc.code), detail

    def _log_dispatch(
        self,
        conn: sqlite3.Connection,
        *,
        notification_id: int,
        channel: str,
        status: str,
        detail: str,
        ts: datetime,
    ) -> None:
        conn.execute(
            "INSERT INTO dispatch_log (notification_id, channel, status, detail, ts) VALUES (?, ?, ?, ?, ?)",
            (notification_id, channel, status, detail, ts.isoformat()),
        )
