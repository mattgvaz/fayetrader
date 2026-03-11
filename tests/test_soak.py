from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.services.chat_store import ChatStore
from app.services.engine import TradingEngine
from app.services.event_store import EventStore
from app.services.learning_store import LearningStore
from app.services.model_state_store import ModelStateStore
from app.services.notification_center import NotificationCenter


def _isolated_engine(tmp_path: Path) -> TradingEngine:
    original_market = settings.faye_market_data_adapter
    original_broker = settings.faye_broker_adapter
    try:
        settings.faye_market_data_adapter = "mock"
        settings.faye_broker_adapter = "paper"
        engine = TradingEngine()
    finally:
        settings.faye_market_data_adapter = original_market
        settings.faye_broker_adapter = original_broker
    engine.event_store = EventStore(str(tmp_path / "events.db"))
    engine.notification_center = NotificationCenter(str(tmp_path / "notifications.db"))
    engine.learning_store = LearningStore(str(tmp_path / "learning.db"))
    engine.model_state_store = ModelStateStore(str(tmp_path / "model_state.db"))
    engine.chat_store = ChatStore(str(tmp_path / "chat.db"))
    engine.event_store.create_session(engine.session_id, "2026-03-10T09:30:00")
    engine._load_or_init_model_state()
    if not engine.chat_store.has_sessions():
        engine.create_chat_session(title="Soak Session")
    return engine


def test_generate_live_events_soak_session_completes_without_critical_failures(tmp_path: Path) -> None:
    engine = _isolated_engine(tmp_path)

    total_events = 0
    for _ in range(25):
        events = engine.generate_live_events(decision_limit=25)
        assert events
        total_events += len(events)

    audit = engine.decision_audit(limit=100)
    sessions = engine.run_sessions(limit=10)
    performance = engine.performance_log

    assert total_events >= 25 * 3
    assert len(audit) >= 25
    assert sessions
    assert sessions[0]["session_id"] == engine.session_id
    assert sessions[0]["event_count"] >= total_events
    assert len(performance) >= 26
