"""Tests for the ProfileNormalizer field coercions."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from bharatai.agents.profile_normalizer import ProfileNormalizer
from bharatai.domain.enums import Category, Gender, IndianState, ResidenceType
from bharatai.domain.value_objects import Money

_N = ProfileNormalizer()


def test_coerce_enums_by_value_and_name() -> None:
    assert _N.coerce_gender("Female") is Gender.FEMALE
    assert _N.coerce_category("SC") is Category.SC
    assert _N.coerce_category("General") is Category.GENERAL
    assert _N.coerce_state("Maharashtra") is IndianState.MAHARASHTRA
    assert _N.coerce_state("MH") is IndianState.MAHARASHTRA
    assert _N.coerce_residence("rural") is ResidenceType.RURAL
    assert _N.coerce_gender("alien") is None


def test_coerce_money() -> None:
    assert _N.coerce_money("2,50,000") == Money(amount=Decimal("250000"))
    assert _N.coerce_money(50000) == Money(amount=Decimal("50000"))
    assert _N.coerce_money("-5") is None
    assert _N.coerce_money("abc") is None


def test_coerce_money_rejects_non_finite() -> None:
    assert _N.coerce_money("nan") is None
    assert _N.coerce_money("Infinity") is None
    assert _N.coerce_money(float("inf")) is None
    assert _N.coerce_money(float("nan")) is None


def test_coerce_date() -> None:
    assert _N.coerce_date("01/06/1990") == date(1990, 6, 1)
    assert _N.coerce_date("not a date") is None


def test_coerce_bool_and_int() -> None:
    assert _N.coerce_bool("yes") is True
    assert _N.coerce_bool("0") is False
    assert _N.coerce_bool("maybe") is None
    assert _N.coerce_int_in_range("40", 0, 100) == 40
    assert _N.coerce_int_in_range("150", 0, 100) is None


def test_coerce_mobile_and_languages() -> None:
    assert _N.coerce_mobile("+91 98765 43210") == "9876543210"
    assert _N.coerce_mobile("098765 43210") == "9876543210"
    assert _N.coerce_mobile("123") is None
    assert _N.coerce_languages("hi, en") == ["hi", "en"]
    assert _N.coerce_languages(["ta", "te"]) == ["ta", "te"]
