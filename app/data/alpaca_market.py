from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

from app.core.time import utc_now
from app.models.types import MarketTick


class AlpacaMarketDataAdapter:
    def __init__(
        self,
        *,
        api_key_id: str,
        api_secret: str,
        base_url: str = "https://data.alpaca.markets",
        timeout_seconds: float = 3.0,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.25,
    ) -> None:
        self.api_key_id = api_key_id.strip()
        self.api_secret = api_secret.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = max(0.1, float(timeout_seconds))
        self.max_retries = max(0, int(max_retries))
        self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))
        self._fallback_prices: dict[str, float] = {
            "AAPL": 190.0,
            "MSFT": 420.0,
            "SPY": 520.0,
        }

    def latest(self, symbol: str) -> MarketTick:
        ticker = symbol.upper().strip()
        price = self._fetch_latest_price(ticker) if self._has_credentials() else self._fallback_prices.get(ticker, 100.0)
        self._fallback_prices[ticker] = price
        return MarketTick(symbol=ticker, price=price, ts=utc_now())

    def snapshot(self, symbols: list[str]) -> dict[str, float]:
        return {s: self.latest(s).price for s in symbols}

    def _has_credentials(self) -> bool:
        return bool(self.api_key_id and self.api_secret)

    def _fetch_latest_price(self, symbol: str) -> float:
        url = f"{self.base_url}/v2/stocks/{urllib.parse.quote(symbol)}/trades/latest"
        request = urllib.request.Request(
            url=url,
            method="GET",
            headers={
                "APCA-API-KEY-ID": self.api_key_id,
                "APCA-API-SECRET-KEY": self.api_secret,
                "Accept": "application/json",
            },
        )
        payload = self._request_json_with_retries(request)
        if payload is None:
            return self._fallback_prices.get(symbol, 100.0)
        trade = payload.get("trade") if isinstance(payload, dict) else {}
        try:
            return float(trade.get("p"))
        except Exception:  # noqa: BLE001
            return self._fallback_prices.get(symbol, 100.0)

    def _request_json_with_retries(self, request: urllib.request.Request) -> object | None:
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                    return json.loads(response.read().decode("utf-8"))
            except Exception:  # noqa: BLE001
                if attempt >= self.max_retries:
                    break
                if self.retry_backoff_seconds > 0:
                    time.sleep(self.retry_backoff_seconds * (attempt + 1))
        return None
