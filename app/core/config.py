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


settings = Settings()
