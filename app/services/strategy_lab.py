from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models.types import AgentDecision, DecisionAction


@dataclass(frozen=True)
class StrategyAssignment:
    strategy_id: str
    strategy_variant: str
    experiment_bucket: str


class StrategyLab:
    def __init__(self) -> None:
        self._variants: list[dict[str, str]] = [
            {
                "strategy_id": "momentum_v1",
                "strategy_variant": "control",
                "description": "Baseline momentum stub policy.",
            },
            {
                "strategy_id": "mean_reversion_v1",
                "strategy_variant": "challenger",
                "description": "Counter-move challenger for A/B harness.",
            },
        ]
        self._strategy_scores: dict[str, float] = {
            "momentum_v1": 0.5,
            "mean_reversion_v1": 0.5,
        }
        self._model_version_id: int = 1

    def registry(self) -> list[dict[str, str]]:
        return [
            {
                **dict(item),
                "score": round(self._strategy_scores.get(str(item["strategy_id"]), 0.5), 4),
                "model_version_id": self._model_version_id,
            }
            for item in self._variants
        ]

    def strategy_ids(self) -> list[str]:
        return [str(item["strategy_id"]) for item in self._variants]

    def model_state(self) -> dict[str, Any]:
        return {
            "version_id": self._model_version_id,
            "strategy_scores": dict(self._strategy_scores),
        }

    def set_model_state(self, *, version_id: int, strategy_scores: dict[str, float]) -> None:
        normalized = dict(self._strategy_scores)
        for key, value in strategy_scores.items():
            normalized[str(key)] = max(0.0, min(1.0, float(value)))
        self._strategy_scores = normalized
        self._model_version_id = max(1, int(version_id))

    def assign(self, symbol: str, ts: datetime) -> StrategyAssignment:
        window_bucket = f"{ts:%Y%m%d}-h{ts.hour // 2:02d}"
        token = symbol.upper()
        last = ord(token[-1]) if token else 0
        stable_seed = last + (ts.hour // 2)
        default_variant = self._variants[stable_seed % len(self._variants)]
        best_variant = max(
            self._variants,
            key=lambda item: self._strategy_scores.get(str(item["strategy_id"]), 0.5),
        )
        default_score = self._strategy_scores.get(str(default_variant["strategy_id"]), 0.5)
        best_score = self._strategy_scores.get(str(best_variant["strategy_id"]), 0.5)
        variant = best_variant if (best_score - default_score) >= 0.12 else default_variant
        return StrategyAssignment(
            strategy_id=str(variant["strategy_id"]),
            strategy_variant=str(variant["strategy_variant"]),
            experiment_bucket=window_bucket,
        )

    def decide(
        self,
        assignment: StrategyAssignment,
        symbol: str,
        mark_price: float,
        current_qty: int = 0,
    ) -> AgentDecision:
        rounded = int(mark_price)
        score = self._strategy_scores.get(assignment.strategy_id, 0.5)
        confidence_multiplier = 0.75 + (0.5 * score)
        if assignment.strategy_id == "momentum_v1":
            if current_qty > 0 and rounded % 4 == 0:
                return AgentDecision(
                    symbol=symbol,
                    action=DecisionAction.SELL,
                    qty=min(1, current_qty),
                    confidence=min(0.99, 0.57 * confidence_multiplier),
                    reason=f"Momentum control: taking profit on checkpoint (model v{self._model_version_id}, score={score:.2f}).",
                )
            if rounded % 2 == 0:
                return AgentDecision(
                    symbol=symbol,
                    action=DecisionAction.HOLD,
                    qty=0,
                    confidence=min(0.99, 0.50 * confidence_multiplier),
                    reason=f"Momentum control: no edge on even-price checkpoint (model v{self._model_version_id}, score={score:.2f}).",
                )
            return AgentDecision(
                symbol=symbol,
                action=DecisionAction.BUY,
                qty=1,
                confidence=min(0.99, 0.53 * confidence_multiplier),
                reason=f"Momentum control: odd-price continuation candidate (model v{self._model_version_id}, score={score:.2f}).",
            )

        if assignment.strategy_id == "mean_reversion_v1":
            if current_qty > 0 and (rounded % 3 == 0 or rounded % 5 == 0):
                return AgentDecision(
                    symbol=symbol,
                    action=DecisionAction.SELL,
                    qty=min(1, current_qty),
                    confidence=min(0.99, 0.58 * confidence_multiplier),
                    reason=f"Mean-reversion challenger: exit on rebound checkpoint (model v{self._model_version_id}, score={score:.2f}).",
                )
            if rounded % 2 == 0:
                return AgentDecision(
                    symbol=symbol,
                    action=DecisionAction.BUY,
                    qty=1,
                    confidence=min(0.99, 0.56 * confidence_multiplier),
                    reason=f"Mean-reversion challenger: even-price dip-buy setup (model v{self._model_version_id}, score={score:.2f}).",
                )
            return AgentDecision(
                symbol=symbol,
                action=DecisionAction.HOLD,
                qty=0,
                confidence=min(0.99, 0.49 * confidence_multiplier),
                reason=f"Mean-reversion challenger: stand down on extension risk (model v{self._model_version_id}, score={score:.2f}).",
            )

        return AgentDecision(
            symbol=symbol,
            action=DecisionAction.HOLD,
            qty=0,
            confidence=0.4,
            reason="Unknown strategy assignment; forced hold.",
        )

    def attribution(self, decision_log: list[dict[str, str | float | int]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for record in decision_log:
            strategy_id = str(record.get("strategy_id", "unknown"))
            variant = str(record.get("strategy_variant", "unknown"))
            key = (strategy_id, variant)
            bucket = grouped.setdefault(
                key,
                {
                    "strategy_id": strategy_id,
                    "strategy_variant": variant,
                    "decisions": 0,
                    "filled": 0,
                    "blocked": 0,
                    "skipped": 0,
                    "realized_pnl": 0.0,
                    "wins": 0,
                    "losses": 0,
                    "hit_rate": 0.0,
                    "max_drawdown_pct": 0.0,
                    "current_model_score": round(self._strategy_scores.get(strategy_id, 0.5), 4),
                },
            )
            bucket["decisions"] += 1
            status = str(record.get("status", ""))
            if status == "filled":
                bucket["filled"] += 1
            elif status == "blocked":
                bucket["blocked"] += 1
            elif status == "skipped":
                bucket["skipped"] += 1

            pnl_delta = float(record.get("realized_pnl_delta", 0.0) or 0.0)
            bucket["realized_pnl"] += pnl_delta
            if pnl_delta > 0:
                bucket["wins"] += 1
            elif pnl_delta < 0:
                bucket["losses"] += 1

            dd = float(record.get("drawdown_pct", 0.0) or 0.0)
            bucket["max_drawdown_pct"] = max(float(bucket["max_drawdown_pct"]), dd)

        results: list[dict[str, Any]] = []
        for row in grouped.values():
            outcomes = int(row["wins"]) + int(row["losses"])
            row["hit_rate"] = round(int(row["wins"]) / outcomes, 4) if outcomes > 0 else 0.0
            row["realized_pnl"] = round(float(row["realized_pnl"]), 4)
            row["max_drawdown_pct"] = round(float(row["max_drawdown_pct"]), 4)
            results.append(row)
        return sorted(results, key=lambda item: (int(item["filled"]), float(item["realized_pnl"])), reverse=True)
