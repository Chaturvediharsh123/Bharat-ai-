"""Unit tests for domain value objects (Money paise round-trip, validators)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from bharatai.domain.enums import IndianState
from bharatai.domain.value_objects import Address, DateRange, Money


@pytest.mark.parametrize(
    ("rupees", "paise"),
    [("0.00", 0), ("99.99", 9999), ("50000.00", 5_000_000), ("12345.67", 1_234_567)],
)
def test_money_paise_roundtrip(rupees: str, paise: int) -> None:
    money = Money(amount=Decimal(rupees))
    assert money.to_paise() == paise
    assert Money.from_paise(paise).amount == Decimal(rupees)


def test_money_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        Money(amount=Decimal("-1.00"))


def test_daterange_rejects_reversed() -> None:
    with pytest.raises(ValidationError):
        DateRange(start=date(2025, 5, 1), end=date(2025, 1, 1))


def test_daterange_contains() -> None:
    window = DateRange(start=date(2025, 1, 1), end=date(2025, 12, 31))
    assert window.contains(date(2025, 6, 1))
    assert not window.contains(date(2024, 12, 31))


def test_address_pincode_validation() -> None:
    with pytest.raises(ValidationError):
        Address(pincode="12")
    ok = Address(pincode="560001", state=IndianState.KARNATAKA)
    assert ok.pincode == "560001"
