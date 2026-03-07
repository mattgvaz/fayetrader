from __future__ import annotations

from datetime import datetime

from app.models.types import Fill, Order


class PaperBroker:
    def submit_order(self, order: Order, mark_price: float, now: datetime) -> Fill:
        # Simple fill model: immediate execution at mark (plus tiny slippage).
        slippage_bps = 1
        slip = mark_price * (slippage_bps / 10_000)
        fill_price = mark_price + slip if order.side.value == "buy" else mark_price - slip
        return Fill(
            symbol=order.symbol,
            side=order.side,
            qty=order.qty,
            price=fill_price,
            ts=now,
        )
