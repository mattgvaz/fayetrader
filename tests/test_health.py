def test_health(client) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["mode"] == "practice"
    assert "market_data_adapter" in body
    assert "broker_adapter" in body
def test_adapters_endpoint(client) -> None:
    res = client.get("/api/adapters")
    assert res.status_code == 200
    body = res.json()
    assert "market_data_adapter" in body
    assert "broker_adapter" in body
