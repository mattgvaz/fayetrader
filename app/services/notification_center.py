from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class NotificationCenter:
    def __init__(self, db_path: str = "app/data/runtime_notifications.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
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
                    email_to TEXT NOT NULL DEFAULT ''
                )
                """
            )
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

    def channels(self) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM channel_settings WHERE id = 1").fetchone()
        if row is None:
            return {
                "in_app_enabled": True,
                "webhook_enabled": False,
                "webhook_url": "",
                "email_enabled": False,
                "email_to": "",
            }
        return {
            "in_app_enabled": bool(row["in_app_enabled"]),
            "webhook_enabled": bool(row["webhook_enabled"]),
            "webhook_url": str(row["webhook_url"] or ""),
            "email_enabled": bool(row["email_enabled"]),
            "email_to": str(row["email_to"] or ""),
        }

    def update_channels(
        self,
        *,
        in_app_enabled: bool,
        webhook_enabled: bool,
        webhook_url: str,
        email_enabled: bool,
        email_to: str,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE channel_settings
                SET in_app_enabled = ?, webhook_enabled = ?, webhook_url = ?, email_enabled = ?, email_to = ?
                WHERE id = 1
                """,
                (1 if in_app_enabled else 0, 1 if webhook_enabled else 0, webhook_url, 1 if email_enabled else 0, email_to),
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
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO notifications (created_at, kind, symbol, title, body, score, threshold, acknowledged, snoozed_until)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL)
                """,
                (ts.isoformat(), "hot_opportunity", symbol, title, body, float(score), float(threshold)),
            )
            notif_id = int(cur.lastrowid or 0)
            settings = self.channels()
            if settings["webhook_enabled"]:
                webhook_url = settings["webhook_url"].strip()
                status = "queued_scaffold" if webhook_url else "skipped_missing_webhook_url"
                detail = webhook_url if webhook_url else "No webhook_url configured."
                conn.execute(
                    "INSERT INTO dispatch_log (notification_id, channel, status, detail, ts) VALUES (?, ?, ?, ?, ?)",
                    (notif_id, "webhook", status, detail, ts.isoformat()),
                )
            if settings["email_enabled"]:
                email_to = settings["email_to"].strip()
                status = "queued_scaffold" if email_to else "skipped_missing_email"
                detail = email_to if email_to else "No email_to configured."
                conn.execute(
                    "INSERT INTO dispatch_log (notification_id, channel, status, detail, ts) VALUES (?, ?, ?, ?, ?)",
                    (notif_id, "email", status, detail, ts.isoformat()),
                )
            conn.commit()
        return self.get_notification(self._public_id(notif_id)) or {}

    def list_notifications(self, limit: int = 50, include_acknowledged: bool = False) -> list[dict[str, Any]]:
        now_iso = datetime.utcnow().isoformat()
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
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_notification(row) for row in rows]

    def get_notification(self, notification_id: str) -> dict[str, Any] | None:
        parsed = self._parse_id(notification_id)
        if parsed is None:
            return None
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM notifications WHERE id = ?", (parsed,)).fetchone()
        return self._row_to_notification(row) if row else None

    def acknowledge(self, notification_id: str) -> dict[str, Any] | None:
        parsed = self._parse_id(notification_id)
        if parsed is None:
            return None
        with self._connect() as conn:
            conn.execute("UPDATE notifications SET acknowledged = 1 WHERE id = ?", (parsed,))
            conn.commit()
        return self.get_notification(notification_id)

    def snooze(self, notification_id: str, minutes: int) -> dict[str, Any] | None:
        parsed = self._parse_id(notification_id)
        if parsed is None:
            return None
        until = (datetime.utcnow() + timedelta(minutes=max(1, minutes))).isoformat()
        with self._connect() as conn:
            conn.execute("UPDATE notifications SET snoozed_until = ? WHERE id = ?", (until, parsed))
            conn.commit()
        return self.get_notification(notification_id)

    def recent_dispatches(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
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
