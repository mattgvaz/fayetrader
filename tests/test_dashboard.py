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
    assert "metrics" in body
    assert "positions" in body
    assert "recent_decisions" in body


def test_stream_endpoint_validates_interval() -> None:
    client = TestClient(app)
    res = client.get("/api/stream?interval_ms=100")
    assert res.status_code == 400
