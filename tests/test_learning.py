from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app


def test_learning_spec_endpoint() -> None:
    client = TestClient(app)
    res = client.get("/api/learning/spec")
    assert res.status_code == 200
    body = res.json()
    assert "sample_schema" in body
    assert "scoring_weights" in body
    assert "trade_id" in body["sample_schema"]["properties"]


def test_learning_score_endpoint() -> None:
    client = TestClient(app)
    opened_at = datetime.utcnow()
    payload = {
        "trade_id": "t-001",
        "strategy_id": "mean_reversion_v1",
        "strategy_variant": "control",
        "symbol": "AAPL",
        "opened_at": opened_at.isoformat(),
        "closed_at": (opened_at + timedelta(minutes=22)).isoformat(),
        "features": {"volatility_regime": "medium", "spread_bps": 2.4},
        "regime": "range",
        "expected_edge_bps": 12.0,
        "realized_pnl": 48.0,
        "realized_return_pct": 0.32,
        "slippage_bps": 3.0,
        "max_adverse_excursion_pct": 0.55,
        "max_favorable_excursion_pct": 0.9,
        "outcome_label": "win",
    }
    res = client.post("/api/learning/score", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert "score" in body
    assert 0 <= body["score"] <= 1
