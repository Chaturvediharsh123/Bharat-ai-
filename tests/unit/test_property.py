"""Property-based tests for the highest-risk numeric/identifier logic."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from bharatai.domain.value_objects import Money
from bharatai.infrastructure.ocr.parsing import (
    parse_date,
    parse_inr_amount,
    verhoeff_checksum,
    verhoeff_validate,
)


@given(st.integers(min_value=0, max_value=10**12))
def test_money_from_paise_roundtrips(paise: int) -> None:
    assert Money.from_paise(paise).to_paise() == paise


@given(
    st.decimals(
        min_value=Decimal("0"),
        max_value=Decimal("99999999"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    )
)
def test_money_decimal_roundtrips(amount: Decimal) -> None:
    money = Money(amount=amount)
    assert Money.from_paise(money.to_paise()).amount == money.amount


@given(st.integers(min_value=0, max_value=10**11))
def test_verhoeff_generated_number_always_validates(base_int: int) -> None:
    base = str(base_int)
    assert verhoeff_validate(base + str(verhoeff_checksum(base)))


@given(st.integers(min_value=0, max_value=10**12))
def test_parse_inr_amount_plain_integer(value: int) -> None:
    assert parse_inr_amount(str(value)) == Decimal(value)


@given(st.dates(min_value=date(1920, 1, 1), max_value=date(2099, 12, 31)))
def test_parse_date_roundtrips_ddmmyyyy(day: date) -> None:
    assert parse_date(day.strftime("%d/%m/%Y")) == day
