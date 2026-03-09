from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class CatalystTheme(str, Enum):
    AI_DISRUPTION = "ai_disruption"
    EARNINGS = "earnings"
    MACRO = "macro"
    REGULATORY = "regulatory"
    OTHER = "other"


class CatalystImpactDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    MIXED = "mixed"


class CatalystImpact(BaseModel):
    symbol: str = Field(min_length=1)
    direction: CatalystImpactDirection
    opportunity_score: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1)
    setup_hint: str = Field(min_length=1)


class CatalystEvent(BaseModel):
    event_id: str = Field(min_length=1)
    ts: datetime
    source: str = Field(min_length=1)
    headline: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    theme: CatalystTheme = CatalystTheme.OTHER
    urgency: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0, le=1)
    impacts: list[CatalystImpact] = Field(default_factory=list)
