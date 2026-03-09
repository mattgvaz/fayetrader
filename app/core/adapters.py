from __future__ import annotations

from app.brokers.alpaca_paper import AlpacaPaperBroker
from app.brokers.paper import PaperBroker
from app.core.config import settings
from app.data.alpaca_market import AlpacaMarketDataAdapter
from app.data.market import MarketDataAdapter


def select_market_data_adapter() -> tuple[object, str]:
    if settings.market_data_adapter == "alpaca":
        adapter = AlpacaMarketDataAdapter(
            api_key_id=settings.alpaca_api_key_id,
            api_secret=settings.alpaca_api_secret,
            base_url=settings.alpaca_data_base_url,
        )
        return adapter, "alpaca"
    return MarketDataAdapter(), "mock"


def select_broker_adapter() -> tuple[object, str]:
    if settings.mode == "live" and not settings.allow_live_trading:
        return PaperBroker(), "paper_guardrail"
    if settings.broker_adapter == "alpaca_paper":
        adapter = AlpacaPaperBroker(
            api_key_id=settings.alpaca_api_key_id,
            api_secret=settings.alpaca_api_secret,
            base_url=settings.alpaca_trading_base_url,
        )
        return adapter, "alpaca_paper"
    return PaperBroker(), "paper"
