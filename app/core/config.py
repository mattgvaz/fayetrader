import os

from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = "FayeTrader"
    environment: str = "dev"

    # Safety defaults: POC stays in practice mode.
    mode: str = Field(default="practice", pattern="^(practice|live)$")
    symbol_universe: list[str] = ["AAPL", "MSFT", "SPY"]
    starting_cash: float = 100_000.0

    max_position_pct: float = 0.10
    max_daily_loss_pct: float = 0.03
    max_orders_per_minute: int = 10

    market_data_adapter: str = Field(default=os.getenv("FAYE_MARKET_DATA_ADAPTER", "mock"), pattern="^(mock|alpaca)$")
    broker_adapter: str = Field(default=os.getenv("FAYE_BROKER_ADAPTER", "paper"), pattern="^(paper|alpaca_paper)$")

    alpaca_api_key_id: str = os.getenv("ALPACA_API_KEY_ID", "")
    alpaca_api_secret: str = os.getenv("ALPACA_API_SECRET", "")
    alpaca_data_base_url: str = os.getenv("ALPACA_DATA_BASE_URL", "https://data.alpaca.markets")
    alpaca_trading_base_url: str = os.getenv("ALPACA_TRADING_BASE_URL", "https://paper-api.alpaca.markets")

    allow_live_trading: bool = os.getenv("FAYE_ALLOW_LIVE_TRADING", "false").lower() == "true"


settings = Settings()
