from datetime import datetime

from app.models.types import AgentDecision, DecisionAction
from app.services.portfolio import Portfolio
from app.services.risk import RiskEngine


def _decision(action: DecisionAction, qty: int = 10) -> AgentDecision:
    return AgentDecision(symbol="AAPL", action=action, qty=qty, confidence=0.8, reason="test")


def test_hold_is_allowed_without_risk_checks() -> None:
    risk = RiskEngine()
    portfolio = Portfolio(starting_cash=100_000, cash=100_000)
    allowed, reason = risk.allow(_decision(DecisionAction.HOLD), portfolio, 100.0, datetime.utcnow())
    assert allowed is True
    assert reason == "hold"


def test_buy_blocked_when_position_size_exceeds_limit() -> None:
    risk = RiskEngine()
    portfolio = Portfolio(starting_cash=100_000, cash=100_000)
    allowed, reason = risk.allow(_decision(DecisionAction.BUY, qty=300), portfolio, 50.0, datetime.utcnow())
    assert allowed is False
    assert reason == "max_position_size_exceeded"


def test_buy_blocked_at_max_daily_loss() -> None:
    risk = RiskEngine()
    now = datetime.utcnow()
    portfolio = Portfolio(starting_cash=100_000, cash=100_000, daily_realized={now.date(): -3_500.0})
    allowed, reason = risk.allow(_decision(DecisionAction.BUY, qty=1), portfolio, 100.0, now)
    assert allowed is False
    assert reason == "max_daily_loss_reached"


def test_rate_limit_blocks_excess_orders_per_minute() -> None:
    risk = RiskEngine()
    risk.update_controls(
        daily_budget=100_000,
        max_daily_loss_pct=0.03,
        max_position_pct=0.10,
        max_orders_per_minute=2,
    )
    portfolio = Portfolio(starting_cash=100_000, cash=100_000)
    now = datetime.utcnow()
    decision = _decision(DecisionAction.BUY, qty=1)

    first_allowed, _ = risk.allow(decision, portfolio, 100.0, now)
    second_allowed, _ = risk.allow(decision, portfolio, 100.0, now)
    third_allowed, third_reason = risk.allow(decision, portfolio, 100.0, now)

    assert first_allowed is True
    assert second_allowed is True
    assert third_allowed is False
    assert third_reason == "rate_limit_exceeded"
