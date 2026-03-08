from __future__ import annotations

from pydantic import BaseModel, Field


class RiskControls(BaseModel):
    daily_budget: float = Field(gt=0)
    max_position_pct: float = Field(gt=0, le=1)
    max_daily_loss_pct: float = Field(gt=0, le=1)
    max_orders_per_minute: int = Field(ge=1, le=500)


class RiskControlsUpdate(BaseModel):
    daily_budget: float | None = Field(default=None, gt=0)
    max_position_pct: float | None = Field(default=None, gt=0, le=1)
    max_daily_loss_pct: float | None = Field(default=None, gt=0, le=1)
    max_orders_per_minute: int | None = Field(default=None, ge=1, le=500)
