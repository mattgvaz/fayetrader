from __future__ import annotations

from datetime import datetime

from app.core.config import settings
from app.models.types import AgentDecision, DecisionAction
from app.services.portfolio import Portfolio


class RiskEngine:
    def __init__(self) -> None:
        self._order_timestamps: list[datetime] = []

    def _rate_limit_ok(self, now: datetime) -> bool:
        cutoff = now.timestamp() - 60
        self._order_timestamps = [t for t in self._order_timestamps if t.timestamp() >= cutoff]
        return len(self._order_timestamps) < settings.max_orders_per_minute

    def _record_order(self, now: datetime) -> None:
        self._order_timestamps.append(now)

    def allow(self, decision: AgentDecision, portfolio: Portfolio, mark_price: float, now: datetime) -> tuple[bool, str]:
        if decision.action == DecisionAction.HOLD:
            return True, "hold"

        if not self._rate_limit_ok(now):
            return False, "rate_limit_exceeded"

        today_pnl = portfolio.daily_realized.get(now.date(), 0.0)
        max_loss = portfolio.starting_cash * settings.max_daily_loss_pct
        if today_pnl <= -max_loss:
            return False, "max_daily_loss_reached"

        if decision.action == DecisionAction.BUY:
            notional = decision.qty * mark_price
            max_notional = portfolio.total_equity({}) * settings.max_position_pct
            if notional > max_notional:
                return False, "max_position_size_exceeded"
            if notional > portfolio.cash:
                return False, "insufficient_cash"

        self._record_order(now)
        return True, "ok"
