from __future__ import annotations

from datetime import datetime

from app.core.config import settings
from app.models.types import AgentDecision, DecisionAction
from app.services.portfolio import Portfolio


class RiskEngine:
    def __init__(self) -> None:
        self._order_timestamps: list[datetime] = []
        self.daily_budget = settings.starting_cash
        self.max_daily_loss_pct = settings.max_daily_loss_pct
        self.max_position_pct = settings.max_position_pct
        self.max_orders_per_minute = settings.max_orders_per_minute

    def _rate_limit_ok(self, now: datetime) -> bool:
        cutoff = now.timestamp() - 60
        self._order_timestamps = [t for t in self._order_timestamps if t.timestamp() >= cutoff]
        return len(self._order_timestamps) < self.max_orders_per_minute

    def _record_order(self, now: datetime) -> None:
        self._order_timestamps.append(now)

    def controls(self) -> dict[str, float | int]:
        return {
            "daily_budget": self.daily_budget,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_position_pct": self.max_position_pct,
            "max_orders_per_minute": self.max_orders_per_minute,
        }

    def update_controls(
        self,
        *,
        daily_budget: float,
        max_daily_loss_pct: float,
        max_position_pct: float,
        max_orders_per_minute: int,
    ) -> dict[str, float | int]:
        self.daily_budget = daily_budget
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_position_pct = max_position_pct
        self.max_orders_per_minute = max_orders_per_minute
        return self.controls()

    def allow(self, decision: AgentDecision, portfolio: Portfolio, mark_price: float, now: datetime) -> tuple[bool, str]:
        if decision.action == DecisionAction.HOLD:
            return True, "hold"

        if not self._rate_limit_ok(now):
            return False, "rate_limit_exceeded"

        today_pnl = portfolio.daily_realized.get(now.date(), 0.0)
        max_loss = self.daily_budget * self.max_daily_loss_pct
        if today_pnl <= -max_loss:
            return False, "max_daily_loss_reached"

        if decision.action == DecisionAction.BUY:
            notional = decision.qty * mark_price
            risk_capital = min(portfolio.total_equity({}), self.daily_budget)
            max_notional = risk_capital * self.max_position_pct
            if notional > max_notional:
                return False, "max_position_size_exceeded"
            if notional > portfolio.cash:
                return False, "insufficient_cash"

        self._record_order(now)
        return True, "ok"
