from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


EVENT_SCHEMA_VERSION = "2026-03-08"


class EngineEventType(str, Enum):
    DECISION = "decision"
    RISK = "risk"
    ORDER = "order"
    FILL = "fill"
    METRICS = "metrics"
    ALERT = "alert"
    STATE_SNAPSHOT = "state_snapshot"


class EngineEvent(BaseModel):
    schema_version: str = EVENT_SCHEMA_VERSION
    event_type: EngineEventType
    ts: datetime
    data: dict[str, Any]
