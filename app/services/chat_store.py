from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


class ChatStore:
    def __init__(self, db_path: str = "app/data/runtime_chat.db") -> None:
        self.db_path = Path(db_path)
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
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    ts TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def has_sessions(self) -> bool:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM chat_sessions").fetchone()
        return int((row["cnt"] if row else 0) or 0) > 0

    def create_session(self, *, title: str, created_at: str, updated_at: str) -> dict[str, object]:
        session_id = self._next_session_id()
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT INTO chat_sessions (session_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, title, created_at, updated_at),
            )
            conn.commit()
        return self.get_session(session_id) or {}

    def list_sessions(self, *, query: str = "", limit: int = 50) -> list[dict[str, object]]:
        q = query.strip()
        params: list[Any] = []
        where = ""
        if q:
            where = """
                WHERE lower(s.title) LIKE lower(?) OR EXISTS (
                    SELECT 1
                    FROM chat_messages m
                    WHERE m.session_id = s.session_id AND lower(m.content) LIKE lower(?)
                )
            """
            like = f"%{q}%"
            params.extend([like, like])
        params.append(max(1, limit))
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                SELECT s.session_id, s.title, s.created_at, s.updated_at,
                       COUNT(m.id) AS message_count
                FROM chat_sessions s
                LEFT JOIN chat_messages m ON m.session_id = s.session_id
                {where}
                GROUP BY s.session_id
                ORDER BY s.updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [
            {
                "session_id": str(row["session_id"]),
                "title": str(row["title"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
                "message_count": int(row["message_count"] or 0),
            }
            for row in rows
        ]

    def get_session(self, session_id: str) -> dict[str, object] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT session_id, title, created_at, updated_at FROM chat_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not row:
                return None
            messages = conn.execute(
                """
                SELECT role, content, ts
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
        return {
            "session_id": str(row["session_id"]),
            "title": str(row["title"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "messages": [
                {"role": str(m["role"]), "content": str(m["content"]), "ts": str(m["ts"])}
                for m in messages
            ],
        }

    def append_message(self, *, session_id: str, role: str, content: str, ts: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT INTO chat_messages (session_id, role, content, ts) VALUES (?, ?, ?, ?)",
                (session_id, role, content, ts),
            )
            conn.execute("UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?", (ts, session_id))
            conn.commit()

    def update_title(self, *, session_id: str, title: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute("UPDATE chat_sessions SET title = ? WHERE session_id = ?", (title, session_id))
            conn.commit()

    def _next_session_id(self) -> str:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT session_id FROM chat_sessions").fetchall()
        max_seq = 0
        for row in rows:
            raw = str(row["session_id"])
            if raw.startswith("chat-"):
                try:
                    max_seq = max(max_seq, int(raw.split("-", maxsplit=1)[1]))
                except ValueError:
                    continue
        return f"chat-{max_seq + 1:04d}"
