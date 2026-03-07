from __future__ import annotations

from datetime import datetime

from app.models.types import MarketTick


class MarketDataAdapter:
    def __init__(self) -> None:
        self._last: dict[str, float] = {
            "AAPL": 190.0,
            "MSFT": 420.0,
            "SPY": 520.0,
        }

    def latest(self, symbol: str) -> MarketTick:
        price = self._last.get(symbol, 100.0)
        return MarketTick(symbol=symbol, price=price, ts=datetime.utcnow())

    def snapshot(self, symbols: list[str]) -> dict[str, float]:
        return {s: self.latest(s).price for s in symbols}
