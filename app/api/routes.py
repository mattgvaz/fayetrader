from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.services.engine import TradingEngine

router = APIRouter()
engine = TradingEngine()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": settings.mode}


@router.get("/metrics")
def metrics() -> dict[str, float | int]:
    return engine.metrics()


@router.post("/run/{symbol}")
def run(symbol: str) -> dict[str, str | float | int]:
    if symbol not in settings.symbol_universe:
        raise HTTPException(status_code=400, detail=f"Symbol not in universe: {symbol}")
    return engine.run_once(symbol)


@router.get("/decisions")
def decisions(limit: int = 50) -> list[dict[str, str | float | int]]:
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")
    return engine.decision_log[-limit:]
