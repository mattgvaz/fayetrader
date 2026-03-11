from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


class LearningStore:
    def __init__(self, db_path: str = "app/data/runtime_learning.db") -> None:
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
                CREATE TABLE IF NOT EXISTS learning_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    trade_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    strategy_variant TEXT NOT NULL,
                    regime TEXT NOT NULL,
                    expected_edge_bps REAL NOT NULL,
                    realized_pnl REAL NOT NULL,
                    realized_return_pct REAL NOT NULL,
                    features_json TEXT NOT NULL,
                    outcome_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def append(self, event: dict[str, Any]) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO learning_events (
                    ts, trade_id, symbol, strategy_id, strategy_variant, regime,
                    expected_edge_bps, realized_pnl, realized_return_pct, features_json, outcome_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event.get("ts", "")),
                    str(event.get("trade_id", "")),
                    str(event.get("symbol", "")),
                    str(event.get("strategy_id", "")),
                    str(event.get("strategy_variant", "")),
                    str(event.get("regime", "unknown")),
                    float(event.get("expected_edge_bps", 0.0) or 0.0),
                    float(event.get("realized_pnl", 0.0) or 0.0),
                    float(event.get("realized_return_pct", 0.0) or 0.0),
                    json.dumps(event.get("features", {})),
                    json.dumps(event.get("outcome", {})),
                ),
            )
            conn.commit()

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT ts, trade_id, symbol, strategy_id, strategy_variant, regime,
                       expected_edge_bps, realized_pnl, realized_return_pct, features_json, outcome_json
                FROM learning_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            items.append(
                {
                    "ts": str(row["ts"]),
                    "trade_id": str(row["trade_id"]),
                    "symbol": str(row["symbol"]),
                    "strategy_id": str(row["strategy_id"]),
                    "strategy_variant": str(row["strategy_variant"]),
                    "regime": str(row["regime"]),
                    "expected_edge_bps": float(row["expected_edge_bps"] or 0.0),
                    "realized_pnl": float(row["realized_pnl"] or 0.0),
                    "realized_return_pct": float(row["realized_return_pct"] or 0.0),
                    "features": json.loads(str(row["features_json"] or "{}")),
                    "outcome": json.loads(str(row["outcome_json"] or "{}")),
                }
            )
        items.reverse()
        return items
