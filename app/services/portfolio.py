from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.models.types import Fill, Side


@dataclass
class Position:
    qty: int = 0
    avg_cost: float = 0.0


@dataclass
class Portfolio:
    starting_cash: float
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    realized_pnl: float = 0.0
    equity_peak: float = 0.0
    daily_realized: dict[date, float] = field(default_factory=dict)

    def apply_fill(self, fill: Fill) -> None:
        pos = self.positions.setdefault(fill.symbol, Position())
        gross = fill.qty * fill.price

        if fill.side == Side.BUY:
            new_qty = pos.qty + fill.qty
            if new_qty <= 0:
                pos.qty = new_qty
                pos.avg_cost = 0.0 if new_qty == 0 else pos.avg_cost
            else:
                pos.avg_cost = ((pos.qty * pos.avg_cost) + gross) / new_qty
                pos.qty = new_qty
            self.cash -= gross
        else:
            sold_qty = min(fill.qty, max(0, pos.qty))
            pnl = sold_qty * (fill.price - pos.avg_cost)
            self.realized_pnl += pnl
            d = fill.ts.date()
            self.daily_realized[d] = self.daily_realized.get(d, 0.0) + pnl
            pos.qty -= sold_qty
            if pos.qty == 0:
                pos.avg_cost = 0.0
            self.cash += sold_qty * fill.price

    def market_value(self, marks: dict[str, float]) -> float:
        value = 0.0
        for symbol, pos in self.positions.items():
            if pos.qty <= 0:
                continue
            value += pos.qty * marks.get(symbol, pos.avg_cost)
        return value

    def total_equity(self, marks: dict[str, float]) -> float:
        equity = self.cash + self.market_value(marks)
        self.equity_peak = max(self.equity_peak, equity)
        return equity

    def drawdown_pct(self, marks: dict[str, float]) -> float:
        if self.equity_peak <= 0:
            return 0.0
        eq = self.total_equity(marks)
        return max(0.0, (self.equity_peak - eq) / self.equity_peak)
