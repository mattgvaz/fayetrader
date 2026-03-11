from __future__ import annotations

from datetime import UTC, date, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_today() -> date:
    return utc_now().date()
