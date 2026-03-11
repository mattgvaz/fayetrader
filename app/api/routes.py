from __future__ import annotations

import asyncio
import json
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.time import utc_today
from app.models.catalyst import CatalystEvent
from app.models.events import EngineEvent, EngineEventType
from app.models.learning import LearningSample
from app.services.evaluator import SCORING_WEIGHTS, score_learning_sample
from app.services.engine import TradingEngine

router = APIRouter()
engine = TradingEngine()


class ControlsPayload(BaseModel):
    daily_budget: float = Field(gt=0)
    max_daily_loss_pct: float = Field(gt=0, le=1)
    max_position_pct: float = Field(gt=0, le=1)
    max_orders_per_minute: int = Field(ge=1, le=500)


class ChatPayload(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None


class OpportunityPayload(BaseModel):
    threshold: float = Field(ge=0.1, le=10.0)


class NotificationChannelsPayload(BaseModel):
    in_app_enabled: bool = True
    webhook_enabled: bool = False
    webhook_url: str = ""
    email_enabled: bool = False
    email_to: str = ""
    throttle_window_minutes: int = Field(default=10, ge=1, le=240)
    max_notifications_per_window: int = Field(default=3, ge=1, le=50)
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "07:00"
    dedupe_window_minutes: int = Field(default=20, ge=1, le=240)


class NotificationTestPayload(BaseModel):
    message: str = Field(default="Manual test alert from dashboard.", min_length=1, max_length=500)


class ModelUpdatePayload(BaseModel):
    reason: str = Field(default="post_market_update", min_length=1, max_length=200)
    min_samples_per_strategy: int = Field(default=2, ge=1, le=100)
    max_delta_per_update: float = Field(default=0.08, ge=0.01, le=0.5)
    lookback_limit: int = Field(default=500, ge=10, le=5000)


class ModelRollbackPayload(BaseModel):
    target_version_id: int = Field(ge=1)
    reason: str = Field(default="manual_rollback", min_length=1, max_length=200)


def _resolve_date_range(range_key: str, start_date: str | None, end_date: str | None) -> tuple[date, date]:
    today = utc_today()
    if range_key == "this_week":
        return today - timedelta(days=today.weekday()), today
    if range_key == "this_month":
        return today.replace(day=1), today
    if range_key == "last_2_weeks":
        return today - timedelta(days=13), today
    if range_key == "ytd":
        return date(today.year, 1, 1), today
    if range_key == "custom":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="custom range requires start_date and end_date")
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="start_date/end_date must be YYYY-MM-DD") from exc
        if start > end:
            raise HTTPException(status_code=400, detail="start_date must be <= end_date")
        return start, end
    raise HTTPException(status_code=400, detail="range_key must be one of this_week,this_month,last_2_weeks,ytd,custom")


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "mode": settings.mode,
        "market_data_adapter": engine.market_adapter_label,
        "broker_adapter": engine.broker_adapter_label,
    }


@router.get("/adapters")
def adapters() -> dict[str, str]:
    return {
        "market_data_adapter": engine.market_adapter_label,
        "broker_adapter": engine.broker_adapter_label,
    }


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
def state(limit: int = 25) -> dict[str, object]:
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")
    return engine.state(decision_limit=limit)


@router.get("/controls")
def controls() -> dict[str, float | int]:
    return engine.controls()


@router.put("/controls")
def update_controls(payload: ControlsPayload) -> dict[str, float | int]:
    return engine.update_controls(
        daily_budget=payload.daily_budget,
        max_daily_loss_pct=payload.max_daily_loss_pct,
        max_position_pct=payload.max_position_pct,
        max_orders_per_minute=payload.max_orders_per_minute,
    )


@router.get("/stream")
async def stream(interval_ms: int = 1500) -> StreamingResponse:
    if interval_ms < 250:
        raise HTTPException(status_code=400, detail="interval_ms must be >= 250")

    async def event_stream() -> object:
        while True:
            for event in engine.generate_live_events(decision_limit=25):
                payload = json.dumps(event.model_dump(mode="json"))
                yield f"event: engine_event\ndata: {payload}\n\n"
            await asyncio.sleep(interval_ms / 1000)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/event-schema")
def event_schema() -> dict[str, object]:
    return {
        "event_types": [event_type.value for event_type in EngineEventType],
        "schema": EngineEvent.model_json_schema(),
    }


@router.get("/events/recent")
def recent_events(limit: int = 50) -> dict[str, object]:
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")
    return {"events": engine.recent_events(limit=limit)}


@router.get("/sessions")
def sessions(limit: int = 30) -> dict[str, object]:
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")
    return {"sessions": engine.run_sessions(limit=limit)}


@router.get("/sessions/{session_id}/replay")
def replay_session(session_id: str, limit: int = 500) -> dict[str, object]:
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")
    return {"session_id": session_id, "events": engine.replay_session(session_id=session_id, limit=limit)}


@router.get("/decisions/audit")
def decision_audit(session_id: str | None = None, limit: int = 200) -> dict[str, object]:
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")
    return {"audit": engine.decision_audit(session_id=session_id, limit=limit)}


@router.get("/opportunity-controls")
def opportunity_controls() -> dict[str, float]:
    return {"threshold": engine.hot_opportunity_threshold}


@router.put("/opportunity-controls")
def update_opportunity_controls(payload: OpportunityPayload) -> dict[str, float]:
    result = engine.update_hot_opportunity_threshold(payload.threshold)
    return {"threshold": float(result["hot_opportunity_threshold"])}


@router.get("/notifications")
def notifications(limit: int = 50, include_acknowledged: bool = False) -> dict[str, object]:
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")
    return {"notifications": engine.notifications(limit=limit, include_acknowledged=include_acknowledged)}


@router.post("/notifications/{notification_id}/ack")
def acknowledge_notification(notification_id: str) -> dict[str, object]:
    notification = engine.acknowledge_notification(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="notification not found")
    return notification


@router.post("/notifications/{notification_id}/snooze")
def snooze_notification(notification_id: str, minutes: int = 30) -> dict[str, object]:
    notification = engine.snooze_notification(notification_id, minutes=minutes)
    if not notification:
        raise HTTPException(status_code=404, detail="notification not found")
    return notification


@router.get("/notifications/channels")
def notification_channels() -> dict[str, object]:
    return engine.notification_channels()


@router.put("/notifications/channels")
def update_notification_channels(payload: NotificationChannelsPayload) -> dict[str, object]:
    return engine.update_notification_channels(
        in_app_enabled=payload.in_app_enabled,
        webhook_enabled=payload.webhook_enabled,
        webhook_url=payload.webhook_url.strip(),
        email_enabled=payload.email_enabled,
        email_to=payload.email_to.strip(),
        throttle_window_minutes=payload.throttle_window_minutes,
        max_notifications_per_window=payload.max_notifications_per_window,
        quiet_hours_enabled=payload.quiet_hours_enabled,
        quiet_hours_start=payload.quiet_hours_start.strip(),
        quiet_hours_end=payload.quiet_hours_end.strip(),
        dedupe_window_minutes=payload.dedupe_window_minutes,
    )


@router.get("/notifications/dispatches")
def notification_dispatches(limit: int = 50) -> dict[str, object]:
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")
    return {"dispatches": engine.notification_dispatches(limit=limit)}


@router.get("/notifications/metrics")
def notification_metrics(window_hours: int = 24) -> dict[str, object]:
    if window_hours < 1 or window_hours > 168:
        raise HTTPException(status_code=400, detail="window_hours must be between 1 and 168")
    return engine.notification_metrics(window_hours=window_hours)


@router.post("/notifications/test")
def send_notification_test(payload: NotificationTestPayload) -> dict[str, object]:
    return engine.send_test_notification(payload.message.strip())


@router.get("/strategy/registry")
def strategy_registry() -> dict[str, object]:
    return {"strategies": engine.strategy_registry()}


@router.get("/strategy/attribution")
def strategy_attribution(limit: int = 200) -> dict[str, object]:
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")
    return {"attribution": engine.strategy_attribution(limit=limit)}


@router.get("/strategy/model")
def strategy_model_state() -> dict[str, object]:
    return engine.strategy_model_state()


@router.get("/strategy/model/versions")
def strategy_model_versions(limit: int = 50) -> dict[str, object]:
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")
    return {"versions": engine.strategy_model_versions(limit=limit)}


@router.post("/strategy/model/update")
def strategy_model_update(payload: ModelUpdatePayload) -> dict[str, object]:
    return engine.run_strategy_model_update(
        reason=payload.reason.strip(),
        min_samples_per_strategy=payload.min_samples_per_strategy,
        max_delta_per_update=payload.max_delta_per_update,
        lookback_limit=payload.lookback_limit,
    )


@router.post("/strategy/model/rollback")
def strategy_model_rollback(payload: ModelRollbackPayload) -> dict[str, object]:
    rolled = engine.rollback_strategy_model(
        target_version_id=payload.target_version_id,
        reason=payload.reason.strip(),
    )
    if not rolled:
        raise HTTPException(status_code=404, detail="target version not found")
    return rolled


@router.get("/catalyst/schema")
def catalyst_schema() -> dict[str, object]:
    return {"schema": CatalystEvent.model_json_schema()}


@router.get("/catalyst/feed")
def catalyst_feed(limit: int = 5) -> dict[str, object]:
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")
    events = engine.catalyst_events(limit=limit)
    return {"events": [event.model_dump(mode="json") for event in events]}


@router.get("/learning/spec")
def learning_spec() -> dict[str, object]:
    return {
        "sample_schema": LearningSample.model_json_schema(),
        "scoring_weights": SCORING_WEIGHTS,
    }


@router.post("/learning/score")
def learning_score(sample: LearningSample) -> dict[str, float]:
    return score_learning_sample(sample)


@router.get("/learning/events")
def learning_events(limit: int = 100) -> dict[str, object]:
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")
    return {"events": engine.learning_events(limit=limit)}


@router.get("/performance")
def performance(range_key: str = "this_month", start_date: str | None = None, end_date: str | None = None) -> dict[str, object]:
    start, end = _resolve_date_range(range_key, start_date, end_date)
    data = engine.performance(start, end)
    data["range_key"] = range_key
    return data


@router.post("/chat")
def chat(payload: ChatPayload) -> dict[str, object]:
    reply, actions, session = engine.chat(payload.message, payload.session_id)
    return {"reply": reply, "actions": actions, "session": session, "state": engine.state(decision_limit=25)}


@router.post("/chat/sessions")
def create_chat_session(title: str | None = None) -> dict[str, object]:
    return engine.create_chat_session(title=title)


@router.get("/chat/sessions")
def list_chat_sessions(query: str = "", limit: int = 50) -> dict[str, object]:
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")
    return {"sessions": engine.list_chat_sessions(query=query, limit=limit)}


@router.get("/chat/sessions/{session_id}")
def get_chat_session(session_id: str) -> dict[str, object]:
    session = engine.get_chat_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    return session


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>FayeTrader Dashboard</title>
    <link rel="stylesheet" href="/static/dashboard.css?v=20260310">
  </head>
  <body>
    <main class="layout">
      <header class="status">
        <h1 class="brand"><img src="/static/faye-avatar.png" class="brand-avatar" alt="Faye avatar"><span>FayeTrader</span></h1>
        <p id="mode-pill" class="pill">mode: practice</p>
        <p id="stream-pill" class="pill muted">stream: connecting</p>
        <p id="event-pill" class="pill muted">events: waiting</p>
        <p id="stale-pill" class="pill muted">data: stale</p>
      </header>
      <nav class="workflow-tabs" aria-label="Workflow Views">
        <button type="button" data-workflow="pre-market" class="active">Pre-Market</button>
        <button type="button" data-workflow="intraday">Intraday</button>
        <button type="button" data-workflow="post-market">Post-Market</button>
      </nav>
      <p id="workflow-label" class="workflow-label">Pre-Market: verify watchlist, limits, and readiness.</p>
      <div class="workspace">
        <section class="workspace-main">
          <p id="ui-state" class="ui-state">Loading state...</p>

          <section class="workflow-panel active" data-workflow-panel="pre-market">
            <div class="grid">
              <article class="card">
                <h2>Watchlist and Setup Context</h2>
                <table id="watchlist">
                  <thead><tr><th>Symbol</th><th>Premkt Gap</th><th>Volume</th><th>Regime</th><th>Plan</th></tr></thead>
                  <tbody></tbody>
                </table>
              </article>
              <article class="card">
                <h2>Overnight Context</h2>
                <ul id="overnight-context" class="timeline compact"></ul>
              </article>
              <article class="card">
                <h2>Risk Controls</h2>
                <form id="controls" class="controls">
                  <label>Daily Budget <input id="daily-budget" type="number" min="1" step="100"><span class="field-help">Caps total capital the risk engine can allocate during this session.</span></label>
                  <label>Max Daily Loss % <input id="max-daily-loss-pct" type="number" min="0.1" max="100" step="0.1"><span class="field-help">Blocks new trades once realized loss reaches this percent of daily budget.</span></label>
                  <label>Max Position % <input id="max-position-pct" type="number" min="0.1" max="100" step="0.1"><span class="field-help">Limits each new buy order notional to this percent of allowed risk capital.</span></label>
                  <label>Max Orders / Min <input id="max-orders-per-minute" type="number" min="1" max="500" step="1"><span class="field-help">Rate limit for non-hold trade attempts across all symbols each minute.</span></label>
                  <div class="controls-actions">
                    <button type="submit">Save Controls</button>
                    <button type="button" id="controls-reset" class="ghost">Reset</button>
                  </div>
                  <p id="controls-status" class="note">Controls update runtime risk gates immediately.</p>
                </form>
              </article>
              <article class="card">
                <h2>Readiness Checklist</h2>
                <ul id="readiness-checklist" class="timeline compact"></ul>
              </article>
            </div>
          </section>

          <section class="workflow-panel" data-workflow-panel="intraday">
            <div class="grid">
              <article class="card intraday-tape-card">
                <div class="card-head">
                  <h2>Session Tape</h2>
                  <p class="note">Timeline of notable intraday events for rapid scan.</p>
                </div>
                <div id="session-tape" class="session-tape"></div>
              </article>
              <article class="card">
                <div class="card-head">
                  <h2>Hot Opportunity Alerting</h2>
                  <p class="note">In-app alert when score crosses threshold.</p>
                </div>
                <form id="opportunity-controls" class="controls">
                  <label>Alert Threshold
                    <input id="opportunity-threshold" type="number" min="0.1" max="10" step="0.05">
                    <span class="field-help">Score formula is abs(move %) * confidence. Higher threshold means fewer alerts.</span>
                  </label>
                  <div class="controls-actions">
                    <button type="submit">Save Threshold</button>
                  </div>
                  <p id="opportunity-status" class="note">Threshold updates immediately.</p>
                </form>
                <ul id="alert-feed" class="timeline compact"></ul>
              </article>
              <article class="card">
                <div class="card-head">
                  <h2>Notification Center</h2>
                  <p class="note">Acknowledge, snooze, and configure channels.</p>
                </div>
                <form id="notification-channels" class="controls">
                  <label><span>In-App Alerts</span><input id="notify-in-app" type="checkbox" checked></label>
                  <label><span>Webhook Alerts</span><input id="notify-webhook-enabled" type="checkbox"></label>
                  <label>Webhook URL <input id="notify-webhook-url" type="text" placeholder="https://example.com/webhook"></label>
                  <label><span>Email Alerts</span><input id="notify-email-enabled" type="checkbox"></label>
                  <label>Email To <input id="notify-email-to" type="email" placeholder="you@example.com"></label>
                  <label>Throttle Window (min) <input id="notify-throttle-window-minutes" type="number" min="1" max="240" step="1" value="10"></label>
                  <label>Max Alerts / Window <input id="notify-max-per-window" type="number" min="1" max="50" step="1" value="3"></label>
                  <label>Dedupe Window (min) <input id="notify-dedupe-window-minutes" type="number" min="1" max="240" step="1" value="20"></label>
                  <label><span>Quiet Hours</span><input id="notify-quiet-hours-enabled" type="checkbox"></label>
                  <label>Quiet Start (UTC) <input id="notify-quiet-start" type="time" value="22:00"></label>
                  <label>Quiet End (UTC) <input id="notify-quiet-end" type="time" value="07:00"></label>
                  <div class="controls-actions">
                    <button type="submit">Save Channels</button>
                    <button type="button" id="notification-send-test">Send Test Alert</button>
                  </div>
                  <p id="notification-status" class="note">Channel settings update runtime alert routing, throttling, and quiet-hour suppression.</p>
                </form>
                <p id="notification-suppression-summary" class="note">Suppression summary: none in recent dispatch activity.</p>
                <p id="notification-metrics-summary" class="note">24h dispatch metrics: no activity yet.</p>
                <ul id="notification-feed" class="timeline compact"></ul>
                <h3 class="drilldown-h3">Dispatch Activity</h3>
                <ul id="dispatch-feed" class="timeline compact"></ul>
              </article>
              <article class="card">
                <h2>Account</h2>
                <div class="kpis">
                  <p>Cash <strong id="cash">$0.00</strong></p>
                  <p>Equity <strong id="equity">$0.00</strong></p>
                  <p>Realized PnL <strong id="realized">$0.00</strong></p>
                  <p>Drawdown <strong id="drawdown">0.00%</strong></p>
                </div>
              </article>
              <article class="card" id="card-equity">
                <div class="card-head">
                  <h2>Equity and PnL Trend</h2>
                  <button type="button" class="expand-btn" data-expand="equity">Expand</button>
                </div>
                <svg id="equity-chart" viewBox="0 0 440 140" class="chart" role="img" aria-label="Equity trend chart">
                  <polyline id="equity-line" points="" />
                </svg>
                <p id="chart-caption" class="note">Awaiting live equity points...</p>
              </article>
              <article class="card" id="card-positions">
                <div class="card-head">
                  <h2>Open Positions</h2>
                  <button type="button" class="expand-btn" data-expand="positions">Expand</button>
                </div>
                <table id="positions">
                  <thead><tr><th>Symbol</th><th>Qty</th><th>Avg</th><th>Mark</th><th>Unrealized</th></tr></thead>
                  <tbody></tbody>
                </table>
              </article>
              <article class="card" id="card-position-spotlight">
                <h2>Position Spotlight (Learner View)</h2>
                <label class="spotlight-picker">Focus Symbol
                  <select id="position-focus"></select>
                </label>
                <div id="position-spotlight" class="spotlight">
                  Select an open position to see plain-language guidance and risk context.
                </div>
                <button type="button" id="spotlight-inspect" class="expand-btn">Inspect Symbol</button>
                <ul id="position-actions" class="timeline compact"></ul>
              </article>
              <article class="card">
                <h2>Live Research Monitor</h2>
                <div class="research-controls">
                  <label>Source
                    <select id="research-source">
                      <option value="all" selected>All</option>
                      <option value="manual">Manual</option>
                      <option value="auto">Auto</option>
                    </select>
                  </label>
                  <label>Sort
                    <select id="research-sort">
                      <option value="opportunity" selected>Opportunity</option>
                      <option value="confidence">Confidence</option>
                      <option value="move">Price Move</option>
                    </select>
                  </label>
                </div>
                <ul id="research-feed" class="timeline"></ul>
              </article>
              <article class="card">
                <h2>Catalyst Impact Monitor</h2>
                <ul id="catalyst-feed" class="timeline"></ul>
              </article>
              <article class="card">
                <h2>Decision Timeline</h2>
                <ul id="timeline" class="timeline"></ul>
              </article>
              <article class="card">
                <h2>Live Event Bus</h2>
                <ul id="event-feed" class="timeline"></ul>
              </article>
              <article class="card">
                <h2>Decision Inspector</h2>
                <div id="decision-inspector" class="decision-inspector">Select any timeline event to inspect rationale, risk checks, and what changed versus the prior decision.</div>
                <ul id="decision-delta" class="timeline compact"></ul>
              </article>
            </div>
          </section>

          <section class="workflow-panel" data-workflow-panel="post-market">
            <div class="grid">
              <article class="card">
                <h2>Session Summary</h2>
                <div class="kpis">
                  <p>Total Decisions <strong id="session-decisions">0</strong></p>
                  <p>Executed <strong id="session-filled">0</strong></p>
                  <p>Blocked <strong id="session-blocked">0</strong></p>
                  <p>Skipped <strong id="session-skipped">0</strong></p>
                </div>
              </article>
              <article class="card" id="card-performance">
                <div class="card-head">
                  <h2>Performance Tracker</h2>
                  <button type="button" class="expand-btn" data-expand="performance">Expand</button>
                </div>
                <div class="perf-controls">
                  <label>Range
                    <select id="performance-range">
                      <option value="this_week">This Week</option>
                      <option value="this_month" selected>This Month</option>
                      <option value="last_2_weeks">Last 2 Weeks</option>
                      <option value="ytd">YTD</option>
                      <option value="custom">Custom</option>
                    </select>
                  </label>
                  <label id="perf-start-wrap" class="hidden">Start <input id="performance-start" type="date"></label>
                  <label id="perf-end-wrap" class="hidden">End <input id="performance-end" type="date"></label>
                  <button type="button" id="performance-apply">Apply</button>
                </div>
                <svg viewBox="0 0 440 140" class="chart" role="img" aria-label="Performance timeline chart">
                  <polyline id="performance-line" points="" />
                </svg>
                <p id="performance-caption" class="note">Select a range to load timeline.</p>
                <div class="insights-grid">
                  <p>Return <strong id="perf-return">0.00%</strong></p>
                  <p>Realized PnL <strong id="perf-pnl">$0.00</strong></p>
                  <p>Max Drawdown <strong id="perf-dd">0.00%</strong></p>
                  <p>Decisions <strong id="perf-decisions">0</strong></p>
                </div>
              </article>
              <article class="card">
                <h2>Top Outcomes</h2>
                <table id="outcomes">
                  <thead><tr><th>Symbol</th><th>Status</th><th>Action</th><th>Reason</th></tr></thead>
                  <tbody></tbody>
                </table>
              </article>
              <article class="card">
                <h2>Risk Blocks</h2>
                <ul id="risk-blocks" class="timeline compact"></ul>
              </article>
              <article class="card">
                <h2>Next Session Notes</h2>
                <ul id="next-notes" class="timeline compact"></ul>
              </article>
            </div>
          </section>
        </section>

        <aside id="chat-drawer" class="workspace-chat" aria-hidden="true">
          <article class="card chat-card">
            <div class="card-head">
              <h2 class="agent-title"><img src="/static/faye-avatar.png" class="agent-avatar-sm" alt="Faye avatar"><span>Agent Chat</span></h2>
              <button type="button" id="chat-hide" class="expand-btn">Hide</button>
            </div>
            <div class="chat-tools">
              <input id="chat-search" type="text" placeholder="Search chats...">
              <button type="button" id="chat-new">New Chat</button>
            </div>
            <ul id="chat-sessions" class="chat-sessions"></ul>
            <div id="chat-log" class="chat-log"></div>
            <form id="chat-form" class="chat-form">
              <input id="chat-input" type="text" placeholder="Ask: summarize day, add target NVDA, anthropic scenario..." maxlength="2000">
              <button type="submit">Send</button>
            </form>
          </article>
        </aside>
        <div id="chat-drawer-overlay" class="chat-drawer-overlay hidden"></div>
        <button type="button" id="chat-toggle" class="chat-fab" aria-controls="chat-drawer" aria-expanded="false">
          <img src="/static/faye-avatar.png" class="chat-fab-avatar" alt="Faye avatar">
          Chat
          <span id="chat-unread-badge" class="chat-unread hidden">0</span>
        </button>
      </div>
      <div id="expand-modal" class="expand-modal hidden" aria-hidden="true">
        <div id="expand-backdrop" class="expand-backdrop"></div>
        <section class="expand-panel">
          <header class="expand-head">
            <h2 id="expand-title">Detail View</h2>
            <button type="button" id="expand-close">Close</button>
          </header>
          <div id="expand-body" class="expand-body"></div>
        </section>
      </div>
      <div id="drilldown-modal" class="expand-modal hidden" aria-hidden="true">
        <div id="drilldown-backdrop" class="expand-backdrop"></div>
        <section class="expand-panel drilldown-panel">
          <header class="expand-head">
            <h2 id="drilldown-title">Symbol Drilldown</h2>
            <div class="drilldown-actions">
              <button type="button" id="drilldown-open-yahoo">Open in Yahoo Finance</button>
              <button type="button" id="drilldown-close">Close</button>
            </div>
          </header>
          <div class="drilldown-grid">
            <article class="card">
              <h3 class="drilldown-h3">Mini Price Trend</h3>
              <svg viewBox="0 0 920 260" class="chart expanded-chart" role="img" aria-label="Drilldown mini chart">
                <polyline id="drilldown-line" points="" />
              </svg>
              <p id="drilldown-caption" class="note">Waiting for symbol data...</p>
            </article>
            <article class="card">
              <h3 class="drilldown-h3">Thesis Timeline</h3>
              <ul id="drilldown-thesis" class="timeline"></ul>
            </article>
            <article class="card">
              <h3 class="drilldown-h3">Risk History</h3>
              <ul id="drilldown-risk" class="timeline"></ul>
            </article>
            <article class="card">
              <h3 class="drilldown-h3">Ask Faye</h3>
              <div id="drilldown-prompts" class="drilldown-prompts"></div>
            </article>
          </div>
        </section>
      </div>
    </main>
    <script src="/static/dashboard.js?v=20260310"></script>
  </body>
</html>
"""
