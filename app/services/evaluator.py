from __future__ import annotations

from app.models.learning import LearningSample


SCORING_WEIGHTS = {
    "pnl_quality": 0.45,
    "edge_realization": 0.25,
    "execution_quality": 0.15,
    "risk_discipline": 0.15,
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def score_learning_sample(sample: LearningSample) -> dict[str, float]:
    pnl_quality = _clamp01((sample.realized_return_pct + 2.0) / 4.0)
    edge_realization = _clamp01(0.5 + ((sample.realized_return_pct * 100.0) - sample.expected_edge_bps) / 200.0)
    execution_quality = _clamp01(1.0 - (abs(sample.slippage_bps) / 50.0))
    risk_discipline = _clamp01(1.0 - max(0.0, sample.max_adverse_excursion_pct) / 5.0)

    score = (
        pnl_quality * SCORING_WEIGHTS["pnl_quality"]
        + edge_realization * SCORING_WEIGHTS["edge_realization"]
        + execution_quality * SCORING_WEIGHTS["execution_quality"]
        + risk_discipline * SCORING_WEIGHTS["risk_discipline"]
    )
    return {
        "pnl_quality": round(pnl_quality, 4),
        "edge_realization": round(edge_realization, 4),
        "execution_quality": round(execution_quality, 4),
        "risk_discipline": round(risk_discipline, 4),
        "score": round(score, 4),
    }
