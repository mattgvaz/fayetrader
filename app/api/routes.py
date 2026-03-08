from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse

from app.core.config import settings
from app.models.controls import RiskControls, RiskControlsUpdate
from app.models.dashboard import EngineState, StreamEvent
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


@router.get("/state")
def state(limit: int = 25) -> EngineState:
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")
    return EngineState.model_validate(engine.state(decision_limit=limit))


@router.get("/controls")
def controls() -> RiskControls:
    return engine.get_controls()


@router.put("/controls")
def update_controls(update: RiskControlsUpdate) -> RiskControls:
    return engine.update_controls(update)


@router.get("/schema")
def schema() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "state": EngineState.model_json_schema(),
        "stream_event": StreamEvent.model_json_schema(),
    }


@router.get("/stream")
async def stream(interval_ms: int = 1500) -> StreamingResponse:
    if interval_ms < 250:
        raise HTTPException(status_code=400, detail="interval_ms must be >= 250")

    async def event_stream() -> object:
        while True:
            event = StreamEvent(
                schema_version="1.0",
                type="state",
                ts=datetime.now(UTC).isoformat(),
                data=EngineState.model_validate(engine.state(decision_limit=25)),
            )
            payload = event.model_dump_json()
            yield f"event: state\ndata: {payload}\n\n"
            await asyncio.sleep(interval_ms / 1000)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>FayeTrader Dashboard</title>
    <link rel="stylesheet" href="/static/dashboard.css">
  </head>
  <body>
    <main class="layout">
      <header class="status">
        <h1>FayeTrader</h1>
        <p id="mode-pill" class="pill">mode: practice</p>
        <p id="stream-pill" class="pill muted">stream: connecting</p>
      </header>
      <section class="grid">
        <article class="card">
          <h2>Account</h2>
          <div class="kpis">
            <p>Cash <strong id="cash">$0.00</strong></p>
            <p>Equity <strong id="equity">$0.00</strong></p>
            <p>Realized PnL <strong id="realized">$0.00</strong></p>
            <p>Drawdown <strong id="drawdown">0.00%</strong></p>
          </div>
        </article>
        <article class="card">
          <h2>Risk Controls</h2>
          <form id="controls" class="controls">
            <label>Daily Budget <input id="daily-budget" type="number" value="100000"></label>
            <label>Max Daily Loss % <input id="max-daily-loss" type="number" step="0.1" value="3"></label>
            <label>Max Position % <input id="max-position" type="number" step="0.1" value="10"></label>
            <label>Max Orders/Min <input id="max-orders" type="number" value="10"></label>
            <button id="save-controls" type="submit">Save Controls</button>
            <p id="controls-status" class="note">Edits are enforced immediately by risk checks.</p>
          </form>
        </article>
        <article class="card">
          <h2>Open Positions</h2>
          <table id="positions">
            <thead><tr><th>Symbol</th><th>Qty</th><th>Avg</th><th>Mark</th><th>Unrealized</th></tr></thead>
            <tbody></tbody>
          </table>
        </article>
        <article class="card">
          <h2>Decision Timeline</h2>
          <ul id="timeline" class="timeline"></ul>
        </article>
      </section>
    </main>
    <script src="/static/dashboard.js"></script>
  </body>
</html>
"""
