"""bharatai.infrastructure.db.mappers — centralized domain<->row serialization.

One place defines how each domain type is stored: enums as their ``.value`` TEXT,
Money as integer paise, datetimes/dates as ISO-8601 TEXT, value objects as JSON.
Repositories compose these primitives; they never hand-roll conversions.
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TypeVar

from pydantic import BaseModel

from bharatai.common.exceptions import SerializationError
from bharatai.domain.value_objects import Money

_M = TypeVar("_M", bound=BaseModel)

_PAISE = Decimal(100)


# ── datetimes & dates ────────────────────────────────────────────────────────
def dt_to_iso(value: datetime | None) -> str | None:
    """Serialize a datetime to ISO-8601, normalized to UTC (naive assumed UTC).

    Normalizing aware datetimes to UTC keeps the stored TEXT lexicographically
    sortable, so ``ORDER BY`` on a timestamp column sorts by true instant.
    """
    if value is None:
        return None
    value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return value.isoformat()


def dt_from_iso(value: str | None) -> datetime | None:
    """Parse an ISO-8601 datetime, normalizing to timezone-aware UTC."""
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SerializationError(f"Invalid datetime: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def dt_from_iso_req(value: str) -> datetime:
    """Parse a non-null ISO-8601 datetime column (for NOT NULL timestamp fields)."""
    parsed = dt_from_iso(value)
    if parsed is None:
        raise SerializationError("expected a datetime but column was NULL")
    return parsed


def date_to_iso(value: date | None) -> str | None:
    """Serialize a date to ISO-8601."""
    return value.isoformat() if value is not None else None


def date_from_iso(value: str | None) -> date | None:
    """Parse an ISO-8601 date."""
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SerializationError(f"Invalid date: {value!r}") from exc


# ── money ────────────────────────────────────────────────────────────────────
def money_to_paise(value: Money | None) -> int | None:
    """Serialize Money to integer paise.

    The column form stores paise only (no currency column), so it is INR-only;
    a non-INR Money would silently lose its currency and is rejected loudly.
    """
    if value is None:
        return None
    if value.currency != "INR":
        raise SerializationError(f"column-stored Money must be INR, got {value.currency!r}")
    return value.to_paise()


def money_from_paise(value: int | None) -> Money | None:
    """Build Money from integer paise."""
    return Money.from_paise(value) if value is not None else None


# ── booleans ─────────────────────────────────────────────────────────────────
def bool_to_int(value: bool | None) -> int | None:
    """Serialize a tri-state boolean to 0/1/NULL."""
    return None if value is None else int(value)


def int_to_bool(value: int | None) -> bool | None:
    """Parse 0/1/NULL into a tri-state boolean."""
    return None if value is None else bool(value)


# ── value objects & lists as JSON ────────────────────────────────────────────
def model_to_json(model: BaseModel | None) -> str | None:
    """Serialize a pydantic model to a JSON string (mode='json')."""
    if model is None:
        return None
    return json.dumps(model.model_dump(mode="json"), ensure_ascii=False)


def json_to_model(model_cls: type[_M], raw: str | None) -> _M | None:
    """Parse a JSON string back into the given pydantic model type."""
    if raw is None:
        return None
    try:
        return model_cls.model_validate(json.loads(raw))
    except (ValueError, TypeError) as exc:
        raise SerializationError(f"Invalid JSON for {model_cls.__name__}: {exc}") from exc


def models_to_json(models: list[BaseModel]) -> str:
    """Serialize a list of pydantic models to a JSON array string."""
    return json.dumps([m.model_dump(mode="json") for m in models], ensure_ascii=False)


def json_to_models(model_cls: type[_M], raw: str | None) -> list[_M]:
    """Parse a JSON array string into a list of the given pydantic model type."""
    if raw is None:
        return []
    try:
        return [model_cls.model_validate(item) for item in json.loads(raw)]
    except (ValueError, TypeError) as exc:
        raise SerializationError(f"Invalid JSON list for {model_cls.__name__}: {exc}") from exc


def str_list_to_json(values: list[str]) -> str:
    """Serialize a list of strings to a JSON array string."""
    return json.dumps(values, ensure_ascii=False)


def json_to_str_list(raw: str | None) -> list[str]:
    """Parse a JSON array string into a list of strings."""
    if raw is None:
        return []
    try:
        return [str(v) for v in json.loads(raw)]
    except (ValueError, TypeError) as exc:
        raise SerializationError(f"Invalid JSON string-list: {exc}") from exc
