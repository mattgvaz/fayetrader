from __future__ import annotations

import json
import urllib.request
from datetime import datetime

from app.models.types import Fill, Order


class AlpacaPaperBroker:
    def __init__(
        self,
        *,
        api_key_id: str,
        api_secret: str,
        base_url: str = "https://paper-api.alpaca.markets",
        timeout_seconds: float = 4.0,
    ) -> None:
        self.api_key_id = api_key_id.strip()
        self.api_secret = api_secret.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = max(0.1, float(timeout_seconds))

    def submit_order(self, order: Order, mark_price: float, now: datetime) -> Fill:
        if not self._has_credentials():
            return self._fallback_fill(order=order, mark_price=mark_price, now=now)
        request_payload = {
            "symbol": order.symbol,
            "qty": str(order.qty),
            "side": order.side.value,
            "type": "market",
            "time_in_force": "day",
        }
        body = json.dumps(request_payload).encode("utf-8")
        request = urllib.request.Request(
            url=f"{self.base_url}/v2/orders",
            method="POST",
            data=body,
            headers={
                "APCA-API-KEY-ID": self.api_key_id,
                "APCA-API-SECRET-KEY": self.api_secret,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            return self._fallback_fill(order=order, mark_price=mark_price, now=now)
        fill_price = self._extract_fill_price(payload, fallback=mark_price, side=order.side.value)
        return Fill(
            symbol=order.symbol,
            side=order.side,
            qty=order.qty,
            price=fill_price,
            ts=now,
        )

    def _has_credentials(self) -> bool:
        return bool(self.api_key_id and self.api_secret)

    def _fallback_fill(self, *, order: Order, mark_price: float, now: datetime) -> Fill:
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

    def _extract_fill_price(self, payload: object, *, fallback: float, side: str) -> float:
        if not isinstance(payload, dict):
            return fallback
        try:
            avg = payload.get("filled_avg_price")
            if avg is not None:
                return float(avg)
            limit = payload.get("limit_price")
            if limit is not None:
                return float(limit)
            submitted = payload.get("submitted_at")
            if submitted:
                return fallback
        except Exception:  # noqa: BLE001
            return fallback
        slippage_bps = 1
        slip = fallback * (slippage_bps / 10_000)
        return fallback + slip if side == "buy" else fallback - slip
