from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.api.routes import engine
from app.main import app


def test_dashboard_page_loads() -> None:
    client = TestClient(app)
    res = client.get("/api/dashboard")
    assert res.status_code == 200
    assert "FayeTrader Dashboard" in res.text
    assert "/static/faye-avatar.png" in res.text
    assert "data-workflow-panel=\"pre-market\"" in res.text
    assert "data-workflow-panel=\"intraday\"" in res.text
    assert "data-workflow-panel=\"post-market\"" in res.text
    assert "Equity and PnL Trend" in res.text
    assert "data-expand=\"equity\"" in res.text
    assert "data-expand=\"positions\"" in res.text
    assert "data-expand=\"performance\"" in res.text
    assert "Live Research Monitor" in res.text
    assert "Catalyst Impact Monitor" in res.text
    assert "Position Spotlight (Learner View)" in res.text
    assert "Session Tape" in res.text
    assert "Decision Inspector" in res.text
    assert "research-source" in res.text
    assert "research-sort" in res.text
    assert "event-feed" in res.text
    assert "alert-feed" in res.text
    assert "opportunity-controls" in res.text
    assert "notification-channels" in res.text
    assert "notification-suppression-summary" in res.text
    assert "notification-metrics-summary" in res.text
    assert "notification-send-test" in res.text
    assert "notification-feed" in res.text
    assert "dispatch-feed" in res.text
    assert "notify-throttle-window-minutes" in res.text
    assert "notify-max-per-window" in res.text
    assert "notify-dedupe-window-minutes" in res.text
    assert "notify-quiet-hours-enabled" in res.text
    assert "notify-quiet-start" in res.text
    assert "notify-quiet-end" in res.text
    assert "spotlight-inspect" in res.text
    assert "drilldown-modal" in res.text
    assert "drilldown-prompts" in res.text
    assert "drilldown-open-yahoo" in res.text
    assert "Agent Chat" in res.text
    assert "chat-search" in res.text
    assert "chat-new" in res.text
    assert "chat-toggle" in res.text
    assert "chat-unread-badge" in res.text
    assert "chat-hide" in res.text
    assert "Performance Tracker" in res.text
    assert "Caps total capital the risk engine can allocate during this session." in res.text


def test_root_redirects_to_dashboard() -> None:
    client = TestClient(app)
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 307
    assert res.headers["location"] == "/api/dashboard"


def test_state_payload_shape() -> None:
    client = TestClient(app)
    res = client.get("/api/state")
    assert res.status_code == 200
    body = res.json()
    assert "mode" in body
    assert "metrics" in body
    assert "controls" in body
    assert "positions" in body
    assert "recent_decisions" in body
    assert "research_targets" in body
    assert "catalyst_events" in body
    assert "catalyst_impacts" in body
    assert "strategy_registry" in body
    assert "strategy_attribution" in body


def test_stream_endpoint_validates_interval() -> None:
    client = TestClient(app)
    res = client.get("/api/stream?interval_ms=100")
    assert res.status_code == 400


def test_event_schema_endpoint() -> None:
    client = TestClient(app)
    res = client.get("/api/event-schema")
    assert res.status_code == 200
    body = res.json()
    assert "event_types" in body
    assert "state_snapshot" in body["event_types"]
    assert "alert" in body["event_types"]
    assert "schema" in body
    assert "properties" in body["schema"]


def test_catalyst_schema_endpoint() -> None:
    client = TestClient(app)
    res = client.get("/api/catalyst/schema")
    assert res.status_code == 200
    body = res.json()
    assert "schema" in body
    assert "properties" in body["schema"]


def test_catalyst_feed_endpoint() -> None:
    client = TestClient(app)
    res = client.get("/api/catalyst/feed?limit=3")
    assert res.status_code == 200
    body = res.json()
    assert "events" in body
    assert len(body["events"]) >= 1


def test_engine_snapshot_event_envelope_shape() -> None:
    snapshot = engine.snapshot_event()
    payload = snapshot.model_dump(mode="json")
    assert payload["schema_version"] == "2026-03-08"
    assert payload["event_type"] == "state_snapshot"
    assert "data" in payload
    assert "metrics" in payload["data"]


def test_recent_events_endpoint() -> None:
    engine.generate_live_events()
    client = TestClient(app)
    res = client.get("/api/events/recent?limit=10")
    assert res.status_code == 200
    body = res.json()
    assert "events" in body
    assert len(body["events"]) >= 1


def test_sessions_and_replay_endpoints() -> None:
    client = TestClient(app)
    engine.generate_live_events()
    sessions_res = client.get("/api/sessions?limit=10")
    assert sessions_res.status_code == 200
    sessions = sessions_res.json()["sessions"]
    assert sessions
    session_id = sessions[0]["session_id"]
    replay_res = client.get(f"/api/sessions/{session_id}/replay?limit=50")
    assert replay_res.status_code == 200
    body = replay_res.json()
    assert body["session_id"] == session_id
    assert "events" in body


def test_decision_audit_endpoint() -> None:
    client = TestClient(app)
    client.post("/api/run/AAPL")
    res = client.get("/api/decisions/audit?limit=50")
    assert res.status_code == 200
    body = res.json()
    assert "audit" in body
    assert len(body["audit"]) >= 1
    sample = body["audit"][-1]
    assert "status" in sample
    assert "strategy_id" in sample


def test_opportunity_controls_roundtrip() -> None:
    client = TestClient(app)
    put_res = client.put("/api/opportunity-controls", json={"threshold": 1.75})
    assert put_res.status_code == 200
    assert put_res.json()["threshold"] == 1.75
    get_res = client.get("/api/opportunity-controls")
    assert get_res.status_code == 200
    assert get_res.json()["threshold"] == 1.75


def test_notification_channel_controls_roundtrip() -> None:
    client = TestClient(app)
    payload = {
        "in_app_enabled": True,
        "webhook_enabled": True,
        "webhook_url": "https://example.com/hook",
        "email_enabled": True,
        "email_to": "user@example.com",
        "throttle_window_minutes": 15,
        "max_notifications_per_window": 5,
        "dedupe_window_minutes": 25,
        "quiet_hours_enabled": True,
        "quiet_hours_start": "23:00",
        "quiet_hours_end": "06:30",
    }
    put_res = client.put("/api/notifications/channels", json=payload)
    assert put_res.status_code == 200
    body = put_res.json()
    assert body["webhook_enabled"] is True
    assert body["email_enabled"] is True
    assert body["throttle_window_minutes"] == 15
    assert body["max_notifications_per_window"] == 5
    assert body["dedupe_window_minutes"] == 25
    assert body["quiet_hours_enabled"] is True
    get_res = client.get("/api/notifications/channels")
    assert get_res.status_code == 200
    assert get_res.json()["webhook_url"] == "https://example.com/hook"
    assert get_res.json()["quiet_hours_end"] == "06:30"


def test_notification_ack_and_snooze_flow() -> None:
    client = TestClient(app)
    client.put(
        "/api/notifications/channels",
        json={
            "in_app_enabled": True,
            "webhook_enabled": False,
            "webhook_url": "",
            "email_enabled": False,
            "email_to": "",
            "throttle_window_minutes": 1,
            "max_notifications_per_window": 50,
            "dedupe_window_minutes": 1,
            "quiet_hours_enabled": False,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "07:00",
        },
    )
    symbol = f"TEST{int(datetime.utcnow().timestamp() * 1_000_000)}"
    engine.notification_center.create_hot_opportunity(
        symbol=symbol,
        score=2.2,
        threshold=1.5,
        thesis="Test notification for ack/snooze flow.",
        ts=datetime.utcnow() + timedelta(days=30),
    )
    listed = client.get("/api/notifications?limit=5")
    assert listed.status_code == 200
    notifications = listed.json()["notifications"]
    if not notifications:
        for _ in range(4):
            engine.generate_live_events()
        notifications = client.get("/api/notifications?limit=5").json()["notifications"]
    assert notifications
    notif_id = notifications[0]["notification_id"]

    snooze = client.post(f"/api/notifications/{notif_id}/snooze?minutes=15")
    assert snooze.status_code == 200
    assert snooze.json()["notification_id"] == notif_id

    ack = client.post(f"/api/notifications/{notif_id}/ack")
    assert ack.status_code == 200
    assert ack.json()["acknowledged"] is True


def test_notification_metrics_endpoint_shape() -> None:
    client = TestClient(app)
    res = client.get("/api/notifications/metrics?window_hours=24")
    assert res.status_code == 200
    body = res.json()
    assert body["window_hours"] == 24
    assert "dispatch_counts" in body
    assert "suppressed_total" in body


def test_notification_test_endpoint_creates_notification() -> None:
    client = TestClient(app)
    payload = {"message": "API test alert"}
    res = client.post("/api/notifications/test", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "test_alert"
    assert "notification_id" in body


def test_strategy_registry_endpoint() -> None:
    client = TestClient(app)
    res = client.get("/api/strategy/registry")
    assert res.status_code == 200
    body = res.json()
    assert "strategies" in body
    assert len(body["strategies"]) >= 2


def test_strategy_attribution_endpoint() -> None:
    client = TestClient(app)
    for symbol in ["AAPL", "MSFT", "SPY", "AAPL", "SPY"]:
        client.post(f"/api/run/{symbol}")
    res = client.get("/api/strategy/attribution?limit=200")
    assert res.status_code == 200
    body = res.json()
    assert "attribution" in body
    assert len(body["attribution"]) >= 1
    sample = body["attribution"][0]
    assert "strategy_id" in sample
    assert "strategy_variant" in sample
    assert "hit_rate" in sample
    active_variants = {(row["strategy_id"], row["strategy_variant"]) for row in body["attribution"]}
    assert len(active_variants) >= 1


def test_controls_update_roundtrip() -> None:
    client = TestClient(app)
    payload = {
        "daily_budget": 85_000,
        "max_daily_loss_pct": 0.02,
        "max_position_pct": 0.08,
        "max_orders_per_minute": 12,
    }
    res = client.put("/api/controls", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body == payload

    controls = client.get("/api/controls")
    assert controls.status_code == 200
    assert controls.json() == payload


def test_performance_endpoint() -> None:
    client = TestClient(app)
    res = client.get("/api/performance?range_key=this_month")
    assert res.status_code == 200
    body = res.json()
    assert "points" in body
    assert "insights" in body


def test_performance_custom_range_validation() -> None:
    client = TestClient(app)
    res = client.get("/api/performance?range_key=custom")
    assert res.status_code == 400


def test_chat_add_target_flow() -> None:
    client = TestClient(app)
    res = client.post("/api/chat", json={"message": "add target NVDA"})
    assert res.status_code == 200
    body = res.json()
    assert "reply" in body
    assert "state" in body
    state = body["state"]
    assert "manual_research_targets" in state
    assert "NVDA" in state["manual_research_targets"]


def test_chat_summary_flow() -> None:
    client = TestClient(app)
    res = client.post("/api/chat", json={"message": "summarize day"})
    assert res.status_code == 200
    body = res.json()
    assert "reply" in body
    assert "Today so far:" in body["reply"]


def test_chat_session_endpoints() -> None:
    client = TestClient(app)
    created = client.post("/api/chat/sessions")
    assert created.status_code == 200
    session = created.json()
    session_id = session["session_id"]

    listed = client.get("/api/chat/sessions")
    assert listed.status_code == 200
    assert any(s["session_id"] == session_id for s in listed.json()["sessions"])

    fetched = client.get(f"/api/chat/sessions/{session_id}")
    assert fetched.status_code == 200
    assert fetched.json()["session_id"] == session_id


def test_chat_session_search_matches_message_content() -> None:
    client = TestClient(app)
    created = client.post("/api/chat/sessions", params={"title": "Ops Chat"})
    assert created.status_code == 200
    session_id = created.json()["session_id"]
    marker = "needle-qa-7731"
    posted = client.post("/api/chat", json={"session_id": session_id, "message": f"store marker {marker}"})
    assert posted.status_code == 200
    listed = client.get(f"/api/chat/sessions?query={marker}&limit=20")
    assert listed.status_code == 200
    ids = [s["session_id"] for s in listed.json()["sessions"]]
    assert session_id in ids
