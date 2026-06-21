"""bharatai.common.ids — identifier and UTC-time helpers for adapters/services.

The domain layer self-generates ids/timestamps to stay dependency-free; outer
layers use these helpers so there is one place that defines "a new id" and "now".
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


def new_id() -> str:
    """Return a fresh UUID4 as a string."""
    return str(uuid4())


def now_utc() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)
