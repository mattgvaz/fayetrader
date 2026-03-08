from __future__ import annotations

from datetime import UTC, datetime

from app.agents.trading_agent import TradingAgent
from app.brokers.paper import PaperBroker
from app.core.config import settings
from app.data.market import MarketDataAdapter
from app.models.controls import RiskControls, RiskControlsUpdate
from app.models.types import DecisionAction, Order, OrderType, Side
from app.services.portfolio import Portfolio
from app.services.risk import RiskEngine


class TradingEngine:
    def __init__(self) -> None:
        self.market = MarketDataAdapter()
        self.agent = TradingAgent()
        self.risk = RiskEngine()
        self.broker = PaperBroker()
        self.portfolio = Portfolio(starting_cash=settings.starting_cash, cash=settings.starting_cash)
        self.decision_log: list[dict[str, str | float | int]] = []
        self.controls = RiskControls(
            daily_budget=settings.starting_cash,
            max_position_pct=settings.max_position_pct,
            max_daily_loss_pct=settings.max_daily_loss_pct,
            max_orders_per_minute=settings.max_orders_per_minute,
        )

    def run_once(self, symbol: str) -> dict[str, str | float | int]:
        now = datetime.now(UTC)
        tick = self.market.latest(symbol)
        decision = self.agent.decide(symbol=symbol, mark_price=tick.price)

        record: dict[str, str | float | int] = {
            "symbol": symbol,
            "action": decision.action.value,
            "confidence": decision.confidence,
            "reason": decision.reason,
            "price": tick.price,
            "ts": now.isoformat(),
        }

        if decision.action == DecisionAction.HOLD:
            record["status"] = "skipped"
            self.decision_log.append(record)
            return record

        allowed, gate_reason = self.risk.allow(
            decision,
            self.portfolio,
            tick.price,
            now,
            max_position_pct=self.controls.max_position_pct,
            max_daily_loss_pct=self.controls.max_daily_loss_pct,
            max_orders_per_minute=self.controls.max_orders_per_minute,
            daily_budget=self.controls.daily_budget,
        )
        if not allowed:
            record["status"] = "blocked"
            record["risk_reason"] = gate_reason
            self.decision_log.append(record)
            return record

        order = Order(
            symbol=symbol,
            side=Side.BUY if decision.action == DecisionAction.BUY else Side.SELL,
            qty=decision.qty,
            order_type=OrderType.MARKET,
        )
        fill = self.broker.submit_order(order, tick.price, now)
        self.portfolio.apply_fill(fill)

        record["status"] = "filled"
        record["fill_price"] = fill.price
        record["qty"] = fill.qty
        self.decision_log.append(record)
        return record

    def metrics(self) -> dict[str, float | int]:
        marks = self.market.snapshot(settings.symbol_universe)
        equity = self.portfolio.total_equity(marks)
        return {
            "cash": self.portfolio.cash,
            "market_value": self.portfolio.market_value(marks),
            "equity": equity,
            "realized_pnl": self.portfolio.realized_pnl,
            "drawdown_pct": self.portfolio.drawdown_pct(marks),
            "positions": sum(1 for p in self.portfolio.positions.values() if p.qty > 0),
            "decisions": len(self.decision_log),
        }

    def state(self, decision_limit: int = 25) -> dict[str, object]:
        marks = self.market.snapshot(settings.symbol_universe)
        open_positions: list[dict[str, float | int | str]] = []
        for symbol, pos in self.portfolio.positions.items():
            if pos.qty <= 0:
                continue
            mark = marks.get(symbol, pos.avg_cost)
            open_positions.append(
                {
                    "symbol": symbol,
                    "qty": pos.qty,
                    "avg_cost": pos.avg_cost,
                    "mark": mark,
                    "unrealized_pnl": (mark - pos.avg_cost) * pos.qty,
                }
            )
        return {
            "mode": settings.mode,
            "controls": self.controls.model_dump(),
            "metrics": self.metrics(),
            "positions": open_positions,
            "recent_decisions": self.decision_log[-decision_limit:],
        }

    def get_controls(self) -> RiskControls:
        return self.controls.model_copy()

    def update_controls(self, update: RiskControlsUpdate) -> RiskControls:
        payload = update.model_dump(exclude_none=True)
        self.controls = self.controls.model_copy(update=payload)
        return self.controls
