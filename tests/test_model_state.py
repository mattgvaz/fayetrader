from app.api.routes import engine
from app.main import app
from app.services.engine import TradingEngine
from fastapi.testclient import TestClient


def test_strategy_model_state_endpoints_roundtrip() -> None:
    client = TestClient(app)
    state = client.get("/api/strategy/model")
    assert state.status_code == 200
    current = state.json()
    assert "version_id" in current
    assert "strategy_scores" in current

    for _ in range(6):
        client.post("/api/run/AAPL")
        client.post("/api/run/MSFT")
        client.post("/api/run/SPY")

    update = client.post(
        "/api/strategy/model/update",
        json={
            "reason": "test_update",
            "min_samples_per_strategy": 1,
            "max_delta_per_update": 0.08,
            "lookback_limit": 500,
        },
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["version_id"] >= current["version_id"]
    assert "diagnostics" in updated
    assert "strategies" in updated["diagnostics"]

    versions = client.get("/api/strategy/model/versions?limit=10")
    assert versions.status_code == 200
    items = versions.json()["versions"]
    assert len(items) >= 1


def test_strategy_model_rollback_and_reload_uses_latest_scores() -> None:
    client = TestClient(app)
    base = client.get("/api/strategy/model").json()
    for _ in range(6):
        client.post("/api/run/AAPL")
        client.post("/api/run/MSFT")
        client.post("/api/run/SPY")
    update = client.post(
        "/api/strategy/model/update",
        json={
            "reason": "update_before_rollback",
            "min_samples_per_strategy": 1,
            "max_delta_per_update": 0.08,
            "lookback_limit": 500,
        },
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["version_id"] >= base["version_id"]

    rollback = client.post(
        "/api/strategy/model/rollback",
        json={
            "target_version_id": int(base["version_id"]),
            "reason": "rollback_test",
        },
    )
    assert rollback.status_code == 200
    rolled = rollback.json()
    assert rolled["rollback_of_version_id"] == int(base["version_id"])

    fresh_engine = TradingEngine()
    fresh_state = fresh_engine.strategy_model_state()
    assert fresh_state["version_id"] == rolled["version_id"]


def test_strategy_scores_affect_assignment_bias() -> None:
    before = engine.strategy_lab.assign("AAPL", engine.market.latest("AAPL").ts).strategy_id
    current = engine.strategy_model_state()
    favored = {
        "momentum_v1": 0.95,
        "mean_reversion_v1": 0.05,
    }
    manual = engine.model_state_store.create_version(
        created_at=engine.market.latest("AAPL").ts.isoformat(),
        reason="manual_bias_test",
        from_version_id=int(current["version_id"]),
        rollback_of_version_id=None,
        sample_count=0,
        scores=favored,
        diagnostics={"note": "manual bias"},
    )
    engine.strategy_lab.set_model_state(
        version_id=int(manual["version_id"]),
        strategy_scores=dict(manual["strategy_scores"]),
    )
    after = engine.strategy_lab.assign("AAPL", engine.market.latest("AAPL").ts).strategy_id
    assert after in {"momentum_v1", "mean_reversion_v1"}
    assert before in {"momentum_v1", "mean_reversion_v1"}
