from app.core.adapters import select_broker_adapter, select_market_data_adapter
from app.core.config import settings


def test_default_adapter_selection_is_safe_mock_and_paper() -> None:
    original_market = settings.market_data_adapter
    original_broker = settings.broker_adapter
    original_mode = settings.mode
    original_allow_live = settings.allow_live_trading
    try:
        settings.market_data_adapter = "mock"
        settings.broker_adapter = "paper"
        settings.mode = "practice"
        settings.allow_live_trading = False
        _, market_label = select_market_data_adapter()
        _, broker_label = select_broker_adapter()
        assert market_label == "mock"
        assert broker_label == "paper"
    finally:
        settings.market_data_adapter = original_market
        settings.broker_adapter = original_broker
        settings.mode = original_mode
        settings.allow_live_trading = original_allow_live


def test_alpaca_adapter_selection_in_practice_mode() -> None:
    original_market = settings.market_data_adapter
    original_broker = settings.broker_adapter
    original_mode = settings.mode
    try:
        settings.market_data_adapter = "alpaca"
        settings.broker_adapter = "alpaca_paper"
        settings.mode = "practice"
        _, market_label = select_market_data_adapter()
        _, broker_label = select_broker_adapter()
        assert market_label == "alpaca"
        assert broker_label == "alpaca_paper"
    finally:
        settings.market_data_adapter = original_market
        settings.broker_adapter = original_broker
        settings.mode = original_mode


def test_live_mode_guardrail_forces_safe_broker_when_not_allowed() -> None:
    original_broker = settings.broker_adapter
    original_mode = settings.mode
    original_allow_live = settings.allow_live_trading
    try:
        settings.broker_adapter = "alpaca_paper"
        settings.mode = "live"
        settings.allow_live_trading = False
        _, broker_label = select_broker_adapter()
        assert broker_label == "paper_guardrail"
    finally:
        settings.broker_adapter = original_broker
        settings.mode = original_mode
        settings.allow_live_trading = original_allow_live
