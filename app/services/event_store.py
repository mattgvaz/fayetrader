from __future__ import annotations

import json
import sqlite3
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
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS engine_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def append(self, event: EngineEvent) -> None:
        payload = json.dumps(event.model_dump(mode="json"))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO engine_events (ts, event_type, schema_version, payload)
                VALUES (?, ?, ?, ?)
                """,
                (event.ts.isoformat(), event.event_type.value, event.schema_version, payload),
            )
            conn.commit()

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        if limit < 1:
            return []
        with self._connect() as conn:
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
