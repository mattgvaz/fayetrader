from __future__ import annotations

from pydantic import BaseModel

from app.models.controls import RiskControls


class MetricsState(BaseModel):
    cash: float
    market_value: float
    equity: float
    realized_pnl: float
    drawdown_pct: float
    positions: int
    decisions: int


class PositionState(BaseModel):
    symbol: str
    qty: int
    avg_cost: float
    mark: float
    unrealized_pnl: float


class DecisionState(BaseModel):
    symbol: str
    action: str
    confidence: float
    reason: str
    price: float
    ts: str
    status: str
    risk_reason: str | None = None
    fill_price: float | None = None
    qty: int | None = None


class EngineState(BaseModel):
    mode: str
    controls: RiskControls
    metrics: MetricsState
    positions: list[PositionState]
    recent_decisions: list[DecisionState]


class StreamEvent(BaseModel):
    schema_version: str
    type: str
    ts: str
    data: EngineState
