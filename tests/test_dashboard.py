from fastapi.testclient import TestClient

from app.main import app


def test_dashboard_page_loads() -> None:
    client = TestClient(app)
    res = client.get("/api/dashboard")
    assert res.status_code == 200
    assert "FayeTrader Dashboard" in res.text


def test_state_payload_shape() -> None:
    client = TestClient(app)
    res = client.get("/api/state")
    assert res.status_code == 200
    body = res.json()
    assert "mode" in body
    assert "controls" in body
    assert "metrics" in body
    assert "positions" in body
    assert "recent_decisions" in body


def test_controls_update_round_trip() -> None:
    client = TestClient(app)
    put_res = client.put(
        "/api/controls",
        json={
            "daily_budget": 5000,
            "max_daily_loss_pct": 0.02,
            "max_position_pct": 0.05,
            "max_orders_per_minute": 7,
        },
    )
    assert put_res.status_code == 200
    get_res = client.get("/api/controls")
    assert get_res.status_code == 200
    body = get_res.json()
    assert body["daily_budget"] == 5000
    assert body["max_daily_loss_pct"] == 0.02
    assert body["max_position_pct"] == 0.05
    assert body["max_orders_per_minute"] == 7


def test_schema_endpoint_exposes_versioned_contract() -> None:
    client = TestClient(app)
    res = client.get("/api/schema")
    assert res.status_code == 200
    body = res.json()
    assert body["schema_version"] == "1.0"
    assert "state" in body
    assert "stream_event" in body


def test_stream_endpoint_validates_interval() -> None:
    client = TestClient(app)
    res = client.get("/api/stream?interval_ms=100")
    assert res.status_code == 400


def test_run_symbol_endpoint_records_decision() -> None:
    client = TestClient(app)
    before = client.get("/api/state").json()["metrics"]["decisions"]
    res = client.post("/api/run/AAPL")
    assert res.status_code == 200
    body = res.json()
    assert body["symbol"] == "AAPL"
    after = client.get("/api/state").json()["metrics"]["decisions"]
    assert after == before + 1
