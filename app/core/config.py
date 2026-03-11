from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FayeTrader"
    environment: str = "dev"

    # Safety defaults: POC stays in practice mode.
    mode: str = Field(default="practice", pattern="^(practice|live)$")
    symbol_universe: list[str] = ["AAPL", "MSFT", "SPY"]
    starting_cash: float = 100_000.0

    max_position_pct: float = 0.10
    max_daily_loss_pct: float = 0.03
    max_orders_per_minute: int = 10

    faye_market_data_adapter: str = Field(default="mock", pattern="^(mock|alpaca)$", alias="FAYE_MARKET_DATA_ADAPTER")
    faye_broker_adapter: str = Field(default="paper", pattern="^(paper|alpaca_paper)$", alias="FAYE_BROKER_ADAPTER")

    alpaca_api_key_id: str = Field(default="", alias="ALPACA_API_KEY_ID")
    alpaca_api_secret: str = Field(default="", alias="ALPACA_API_SECRET")
    alpaca_data_base_url: str = Field(default="https://data.alpaca.markets", alias="ALPACA_DATA_BASE_URL")
    alpaca_trading_base_url: str = Field(default="https://paper-api.alpaca.markets", alias="ALPACA_TRADING_BASE_URL")
    alpaca_data_timeout_seconds: float = Field(default=3.0, alias="ALPACA_DATA_TIMEOUT_SECONDS")
    alpaca_trading_timeout_seconds: float = Field(default=4.0, alias="ALPACA_TRADING_TIMEOUT_SECONDS")
    alpaca_request_max_retries: int = Field(default=2, alias="ALPACA_REQUEST_MAX_RETRIES")
    alpaca_retry_backoff_seconds: float = Field(default=0.25, alias="ALPACA_RETRY_BACKOFF_SECONDS")

    allow_live_trading: bool = Field(default=False, alias="FAYE_ALLOW_LIVE_TRADING")

    @property
    def market_data_adapter(self) -> str:
        return self.faye_market_data_adapter

    @property
    def broker_adapter(self) -> str:
        return self.faye_broker_adapter


settings = Settings()
