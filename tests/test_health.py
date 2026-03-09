from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["mode"] == "practice"
    assert "market_data_adapter" in body
    assert "broker_adapter" in body


def test_adapters_endpoint() -> None:
    client = TestClient(app)
    res = client.get("/api/adapters")
    assert res.status_code == 200
    body = res.json()
    assert "market_data_adapter" in body
    assert "broker_adapter" in body
