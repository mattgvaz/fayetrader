from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


class ModelStateStore:
    def __init__(self, db_path: str = "app/data/runtime_model_state.db") -> None:
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
                CREATE TABLE IF NOT EXISTS model_versions (
                    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    from_version_id INTEGER,
                    rollback_of_version_id INTEGER,
                    sample_count INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL,
                    diagnostics_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def ensure_baseline(self, *, created_at: str, scores: dict[str, float]) -> dict[str, Any]:
        current = self.latest()
        if current is not None:
            return current
        return self.create_version(
            created_at=created_at,
            reason="baseline_model_scores",
            from_version_id=None,
            rollback_of_version_id=None,
            sample_count=0,
            scores=scores,
            diagnostics={"note": "Baseline scores initialized."},
        )

    def latest(self) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT version_id, created_at, reason, from_version_id, rollback_of_version_id, sample_count, payload_json, diagnostics_json
                FROM model_versions
                ORDER BY version_id DESC
                LIMIT 1
                """
            ).fetchone()
        return self._row_to_version(row) if row else None

    def list_versions(self, limit: int = 50) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT version_id, created_at, reason, from_version_id, rollback_of_version_id, sample_count, payload_json, diagnostics_json
                FROM model_versions
                ORDER BY version_id DESC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
        return [self._row_to_version(row) for row in rows]

    def get_version(self, version_id: int) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT version_id, created_at, reason, from_version_id, rollback_of_version_id, sample_count, payload_json, diagnostics_json
                FROM model_versions
                WHERE version_id = ?
                """,
                (int(version_id),),
            ).fetchone()
        return self._row_to_version(row) if row else None

    def create_version(
        self,
        *,
        created_at: str,
        reason: str,
        from_version_id: int | None,
        rollback_of_version_id: int | None,
        sample_count: int,
        scores: dict[str, float],
        diagnostics: dict[str, Any],
    ) -> dict[str, Any]:
        payload = json.dumps({"strategy_scores": scores}, sort_keys=True)
        diagnostics_payload = json.dumps(diagnostics, sort_keys=True)
        with closing(self._connect()) as conn:
            cur = conn.execute(
                """
                INSERT INTO model_versions (
                    created_at, reason, from_version_id, rollback_of_version_id, sample_count, payload_json, diagnostics_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    reason,
                    from_version_id,
                    rollback_of_version_id,
                    max(0, int(sample_count)),
                    payload,
                    diagnostics_payload,
                ),
            )
            conn.commit()
            inserted_id = int(cur.lastrowid or 0)
        return self.get_version(inserted_id) or {}

    def _row_to_version(self, row: sqlite3.Row) -> dict[str, Any]:
        payload = json.loads(str(row["payload_json"] or "{}"))
        diagnostics = json.loads(str(row["diagnostics_json"] or "{}"))
        return {
            "version_id": int(row["version_id"]),
            "created_at": str(row["created_at"]),
            "reason": str(row["reason"]),
            "from_version_id": int(row["from_version_id"]) if row["from_version_id"] is not None else None,
            "rollback_of_version_id": (
                int(row["rollback_of_version_id"]) if row["rollback_of_version_id"] is not None else None
            ),
            "sample_count": int(row["sample_count"] or 0),
            "strategy_scores": {
                str(k): float(v)
                for k, v in dict(payload.get("strategy_scores", {})).items()
            },
            "diagnostics": diagnostics,
        }
