from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class OutcomeLabel(str, Enum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


class MarketRegime(str, Enum):
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    RANGE = "range"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


class LearningSample(BaseModel):
    trade_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    strategy_variant: str = Field(default="baseline", min_length=1)
    symbol: str = Field(min_length=1)
    opened_at: datetime
    closed_at: datetime
    features: dict[str, Any] = Field(default_factory=dict)
    regime: MarketRegime = MarketRegime.UNKNOWN
    expected_edge_bps: float = 0.0
    realized_pnl: float
    realized_return_pct: float
    slippage_bps: float = 0.0
    max_adverse_excursion_pct: float = 0.0
    max_favorable_excursion_pct: float = 0.0
    outcome_label: OutcomeLabel
