from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from app.models.events import EngineEvent


class EventStore:
    def __init__(self, db_path: str = "app/data/runtime_events.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_sessions (
                    session_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS engine_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL DEFAULT '',
                    ts TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    status TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    strategy_variant TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            self._ensure_columns(conn)
            conn.commit()

    def _ensure_columns(self, conn: sqlite3.Connection) -> None:
        columns = [str(row[1]) for row in conn.execute("PRAGMA table_info(engine_events)").fetchall()]
        if "session_id" not in columns:
            conn.execute("ALTER TABLE engine_events ADD COLUMN session_id TEXT NOT NULL DEFAULT ''")

    def create_session(self, session_id: str, started_at: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO run_sessions (session_id, started_at) VALUES (?, ?)",
                (session_id, started_at),
            )
            conn.commit()

    def append(self, event: EngineEvent, *, session_id: str) -> None:
        payload = json.dumps(event.model_dump(mode="json"))
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO engine_events (session_id, ts, event_type, schema_version, payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, event.ts.isoformat(), event.event_type.value, event.schema_version, payload),
            )
            conn.commit()

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        if limit < 1:
            return []
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT payload
                FROM engine_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            try:
                events.append(json.loads(str(row[0])))
            except json.JSONDecodeError:
                continue
        events.reverse()
        return events

    def list_sessions(self, limit: int = 30) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT s.session_id, s.started_at, COUNT(e.id) AS event_count
                FROM run_sessions s
                LEFT JOIN engine_events e ON e.session_id = s.session_id
                GROUP BY s.session_id
                ORDER BY s.started_at DESC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
        return [
            {
                "session_id": str(row[0]),
                "started_at": str(row[1]),
                "event_count": int(row[2] or 0),
            }
            for row in rows
        ]

    def replay_session(self, session_id: str, limit: int = 500) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT payload
                FROM engine_events
                WHERE session_id = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (session_id, max(1, limit)),
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            try:
                events.append(json.loads(str(row[0])))
            except json.JSONDecodeError:
                continue
        return events

    def append_decision_audit(self, *, session_id: str, record: dict[str, Any]) -> None:
        ts = str(record.get("ts", ""))
        status = str(record.get("status", "unknown"))
        symbol = str(record.get("symbol", ""))
        action = str(record.get("action", ""))
        strategy_id = str(record.get("strategy_id", ""))
        strategy_variant = str(record.get("strategy_variant", ""))
        payload = json.dumps(record)
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO decision_audit (
                    session_id, ts, status, symbol, action, strategy_id, strategy_variant, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, ts, status, symbol, action, strategy_id, strategy_variant, payload),
            )
            conn.commit()

    def decision_audit(self, session_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if session_id:
            where = "WHERE session_id = ?"
            params.append(session_id)
        params.append(max(1, limit))
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                SELECT payload
                FROM decision_audit
                {where}
                ORDER BY id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            try:
                items.append(json.loads(str(row[0])))
            except json.JSONDecodeError:
                continue
        items.reverse()
        return items
