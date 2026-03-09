from datetime import datetime, timedelta

from app.services.notification_center import NotificationCenter


def test_hot_opportunity_throttle_suppresses_excess_notifications(tmp_path) -> None:
    center = NotificationCenter(db_path=str(tmp_path / "runtime_notifications.db"))
    center.update_channels(
        in_app_enabled=True,
        webhook_enabled=False,
        webhook_url="",
        email_enabled=False,
        email_to="",
        throttle_window_minutes=60,
        max_notifications_per_window=1,
        dedupe_window_minutes=20,
        quiet_hours_enabled=False,
        quiet_hours_start="22:00",
        quiet_hours_end="07:00",
    )
    first = center.create_hot_opportunity(
        symbol="AAPL",
        score=2.1,
        threshold=1.2,
        thesis="First alert should pass.",
        ts=datetime(2026, 3, 8, 13, 0, 0),
    )
    second = center.create_hot_opportunity(
        symbol="MSFT",
        score=2.3,
        threshold=1.2,
        thesis="Second alert should be throttled.",
        ts=datetime(2026, 3, 8, 13, 5, 0),
    )
    assert first["notification_id"].startswith("notif-")
    assert second == {}
    dispatches = center.recent_dispatches(limit=5)
    assert any(d["status"] == "suppressed_throttle" for d in dispatches)


def test_hot_opportunity_quiet_hours_suppresses_in_window(tmp_path) -> None:
    center = NotificationCenter(db_path=str(tmp_path / "runtime_notifications.db"))
    center.update_channels(
        in_app_enabled=True,
        webhook_enabled=False,
        webhook_url="",
        email_enabled=False,
        email_to="",
        throttle_window_minutes=10,
        max_notifications_per_window=5,
        dedupe_window_minutes=20,
        quiet_hours_enabled=True,
        quiet_hours_start="22:00",
        quiet_hours_end="07:00",
    )
    suppressed = center.create_hot_opportunity(
        symbol="NVDA",
        score=2.8,
        threshold=1.4,
        thesis="Should be suppressed in quiet hours.",
        ts=datetime(2026, 3, 8, 23, 30, 0),
    )
    delivered = center.create_hot_opportunity(
        symbol="GOOGL",
        score=2.6,
        threshold=1.4,
        thesis="Should pass outside quiet hours.",
        ts=datetime(2026, 3, 9, 13, 15, 0) + timedelta(seconds=1),
    )
    assert suppressed == {}
    assert delivered["symbol"] == "GOOGL"
    dispatches = center.recent_dispatches(limit=5)
    assert any(d["status"] == "suppressed_quiet_hours" for d in dispatches)


def test_hot_opportunity_dedupe_suppresses_same_symbol_within_window(tmp_path) -> None:
    center = NotificationCenter(db_path=str(tmp_path / "runtime_notifications.db"))
    center.update_channels(
        in_app_enabled=True,
        webhook_enabled=False,
        webhook_url="",
        email_enabled=False,
        email_to="",
        throttle_window_minutes=60,
        max_notifications_per_window=10,
        dedupe_window_minutes=20,
        quiet_hours_enabled=False,
        quiet_hours_start="22:00",
        quiet_hours_end="07:00",
    )
    first = center.create_hot_opportunity(
        symbol="AAPL",
        score=2.4,
        threshold=1.4,
        thesis="First AAPL signal should pass.",
        ts=datetime(2026, 3, 8, 14, 0, 0),
    )
    second = center.create_hot_opportunity(
        symbol="AAPL",
        score=2.6,
        threshold=1.4,
        thesis="Second AAPL signal should be deduped.",
        ts=datetime(2026, 3, 8, 14, 10, 0),
    )
    third = center.create_hot_opportunity(
        symbol="AAPL",
        score=2.7,
        threshold=1.4,
        thesis="Third AAPL signal outside dedupe window should pass.",
        ts=datetime(2026, 3, 8, 14, 25, 1),
    )
    assert first["notification_id"].startswith("notif-")
    assert second == {}
    assert third["notification_id"].startswith("notif-")
    dispatches = center.recent_dispatches(limit=10)
    assert any(d["status"] == "suppressed_dedupe" for d in dispatches)


def test_webhook_dispatch_success_logs_delivered(tmp_path) -> None:
    center = NotificationCenter(
        db_path=str(tmp_path / "runtime_notifications.db"),
        webhook_max_attempts=2,
        webhook_backoff_seconds=0.0,
    )
    center.update_channels(
        in_app_enabled=True,
        webhook_enabled=True,
        webhook_url="https://example.invalid/hook",
        email_enabled=False,
        email_to="",
        throttle_window_minutes=10,
        max_notifications_per_window=5,
        dedupe_window_minutes=20,
        quiet_hours_enabled=False,
        quiet_hours_start="22:00",
        quiet_hours_end="07:00",
    )

    def fake_post(_url: str, _notification: dict[str, object]) -> tuple[int, str]:
        return 200, "ok"

    center._post_webhook = fake_post  # type: ignore[method-assign]
    created = center.create_hot_opportunity(
        symbol="AMD",
        score=2.5,
        threshold=1.4,
        thesis="Webhook success path.",
        ts=datetime(2026, 3, 8, 15, 0, 0),
    )
    assert created["symbol"] == "AMD"
    dispatches = center.recent_dispatches(limit=5)
    assert any(d["status"] == "delivered" for d in dispatches if d["channel"] == "webhook")


def test_webhook_dispatch_retries_and_logs_failed(tmp_path) -> None:
    center = NotificationCenter(
        db_path=str(tmp_path / "runtime_notifications.db"),
        webhook_max_attempts=3,
        webhook_backoff_seconds=0.0,
    )
    center.update_channels(
        in_app_enabled=True,
        webhook_enabled=True,
        webhook_url="https://example.invalid/hook",
        email_enabled=False,
        email_to="",
        throttle_window_minutes=10,
        max_notifications_per_window=5,
        dedupe_window_minutes=20,
        quiet_hours_enabled=False,
        quiet_hours_start="22:00",
        quiet_hours_end="07:00",
    )
    attempts = {"count": 0}

    def fake_post(_url: str, _notification: dict[str, object]) -> tuple[int, str]:
        attempts["count"] += 1
        raise RuntimeError("network down")

    center._post_webhook = fake_post  # type: ignore[method-assign]
    center.create_hot_opportunity(
        symbol="TSLA",
        score=2.7,
        threshold=1.5,
        thesis="Webhook retry path.",
        ts=datetime(2026, 3, 8, 15, 30, 0),
    )
    assert attempts["count"] == 3
    dispatches = center.recent_dispatches(limit=5)
    failed = [d for d in dispatches if d["channel"] == "webhook" and d["status"] == "failed"]
    assert failed
