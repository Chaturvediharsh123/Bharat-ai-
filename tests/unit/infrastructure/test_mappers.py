"""Tests for the DB serialization mappers (None handling + error paths)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from bharatai.common.exceptions import SerializationError
from bharatai.domain.value_objects import Address, Money
from bharatai.infrastructure.db import mappers as m


def test_none_passthroughs() -> None:
    assert m.dt_to_iso(None) is None
    assert m.dt_from_iso(None) is None
    assert m.date_to_iso(None) is None
    assert m.date_from_iso(None) is None
    assert m.money_to_paise(None) is None
    assert m.money_from_paise(None) is None
    assert m.bool_to_int(None) is None
    assert m.int_to_bool(None) is None
    assert m.model_to_json(None) is None
    assert m.json_to_model(Address, None) is None
    assert m.json_to_models(Address, None) == []
    assert m.json_to_str_list(None) == []


def test_bool_and_money_roundtrip() -> None:
    assert m.bool_to_int(True) == 1
    assert m.int_to_bool(0) is False
    money = Money(amount=Decimal("123.45"))
    assert m.money_from_paise(m.money_to_paise(money)) == money


def test_naive_datetime_is_treated_as_utc() -> None:
    iso = m.dt_to_iso(datetime(2026, 1, 1, 12, 0, 0))
    assert iso is not None and iso.endswith("+00:00")
    parsed = m.dt_from_iso("2026-01-01T12:00:00")
    assert parsed is not None and parsed.tzinfo is not None


def test_serialization_errors() -> None:
    with pytest.raises(SerializationError):
        m.dt_from_iso("not-a-date")
    with pytest.raises(SerializationError):
        m.date_from_iso("nope")
    with pytest.raises(SerializationError):
        m.dt_from_iso_req(None)  # type: ignore[arg-type]
    with pytest.raises(SerializationError):
        m.json_to_model(Address, "{bad json")
    with pytest.raises(SerializationError):
        m.json_to_models(Address, "not-json")
    with pytest.raises(SerializationError):
        m.json_to_str_list("not-json")
