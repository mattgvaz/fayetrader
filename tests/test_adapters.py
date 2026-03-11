import json
import urllib.error
import urllib.request
from datetime import datetime

from app.brokers.alpaca_paper import AlpacaPaperBroker
from app.core.adapters import select_broker_adapter, select_market_data_adapter
from app.core.config import settings
from app.data.alpaca_market import AlpacaMarketDataAdapter
from app.models.types import Order, Side


def test_default_adapter_selection_is_safe_mock_and_paper() -> None:
    original_market = settings.faye_market_data_adapter
    original_broker = settings.faye_broker_adapter
    original_mode = settings.mode
    original_allow_live = settings.allow_live_trading
    try:
        settings.faye_market_data_adapter = "mock"
        settings.faye_broker_adapter = "paper"
        settings.mode = "practice"
        settings.allow_live_trading = False
        _, market_label = select_market_data_adapter()
        _, broker_label = select_broker_adapter()
        assert market_label == "mock"
        assert broker_label == "paper"
    finally:
        settings.faye_market_data_adapter = original_market
        settings.faye_broker_adapter = original_broker
        settings.mode = original_mode
        settings.allow_live_trading = original_allow_live


def test_alpaca_adapter_selection_in_practice_mode() -> None:
    original_market = settings.faye_market_data_adapter
    original_broker = settings.faye_broker_adapter
    original_mode = settings.mode
    try:
        settings.faye_market_data_adapter = "alpaca"
        settings.faye_broker_adapter = "alpaca_paper"
        settings.mode = "practice"
        _, market_label = select_market_data_adapter()
        _, broker_label = select_broker_adapter()
        assert market_label == "alpaca"
        assert broker_label == "alpaca_paper"
    finally:
        settings.faye_market_data_adapter = original_market
        settings.faye_broker_adapter = original_broker
        settings.mode = original_mode


def test_live_mode_guardrail_forces_safe_broker_when_not_allowed() -> None:
    original_broker = settings.faye_broker_adapter
    original_mode = settings.mode
    original_allow_live = settings.allow_live_trading
    try:
        settings.faye_broker_adapter = "alpaca_paper"
        settings.mode = "live"
        settings.allow_live_trading = False
        _, broker_label = select_broker_adapter()
        assert broker_label == "paper_guardrail"
    finally:
        settings.faye_broker_adapter = original_broker
        settings.mode = original_mode
        settings.allow_live_trading = original_allow_live


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_alpaca_market_retries_then_uses_recovered_price(monkeypatch) -> None:
    attempts = {"count": 0}

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> _Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise urllib.error.URLError("temporary disconnect")
        return _Response({"trade": {"p": 201.25}})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    adapter = AlpacaMarketDataAdapter(
        api_key_id="key",
        api_secret="secret",
        timeout_seconds=0.1,
        max_retries=2,
        retry_backoff_seconds=0.0,
    )

    tick = adapter.latest("AAPL")

    assert attempts["count"] == 3
    assert tick.price == 201.25


def test_alpaca_market_falls_back_after_retries_exhausted(monkeypatch) -> None:
    attempts = {"count": 0}

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> _Response:
        attempts["count"] += 1
        raise urllib.error.URLError("alpaca unavailable")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    adapter = AlpacaMarketDataAdapter(
        api_key_id="key",
        api_secret="secret",
        timeout_seconds=0.1,
        max_retries=2,
        retry_backoff_seconds=0.0,
    )

    tick = adapter.latest("MSFT")

    assert attempts["count"] == 3
    assert tick.price == 420.0


def test_alpaca_broker_retries_then_uses_remote_fill(monkeypatch) -> None:
    attempts = {"count": 0}

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> _Response:
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise urllib.error.URLError("timeout")
        return _Response({"filled_avg_price": "190.55"})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    broker = AlpacaPaperBroker(
        api_key_id="key",
        api_secret="secret",
        timeout_seconds=0.1,
        max_retries=2,
        retry_backoff_seconds=0.0,
    )

    fill = broker.submit_order(
        Order(symbol="AAPL", side=Side.BUY, qty=1),
        mark_price=190.0,
        now=datetime(2026, 3, 10, 9, 30),
    )

    assert attempts["count"] == 2
    assert fill.price == 190.55


def test_alpaca_broker_falls_back_after_retries_exhausted(monkeypatch) -> None:
    attempts = {"count": 0}

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> _Response:
        attempts["count"] += 1
        raise urllib.error.URLError("bad gateway")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    broker = AlpacaPaperBroker(
        api_key_id="key",
        api_secret="secret",
        timeout_seconds=0.1,
        max_retries=2,
        retry_backoff_seconds=0.0,
    )

    fill = broker.submit_order(
        Order(symbol="AAPL", side=Side.BUY, qty=1),
        mark_price=190.0,
        now=datetime(2026, 3, 10, 9, 30),
    )

    assert attempts["count"] == 3
    assert round(fill.price, 4) == 190.019
