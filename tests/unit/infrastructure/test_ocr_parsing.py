"""Tests for the pure OCR parsing helpers (Verhoeff, INR amounts, dates, ids)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from bharatai.infrastructure.ocr.parsing import (
    find_aadhaar,
    find_pan,
    parse_date,
    parse_inr_amount,
    verhoeff_checksum,
    verhoeff_validate,
)


def test_verhoeff_generate_then_validate() -> None:
    base = "23456789012"  # 11 digits
    full = base + str(verhoeff_checksum(base))
    assert verhoeff_validate(full)


def test_verhoeff_rejects_tampered_and_nondigits() -> None:
    base = "23456789012"
    check = verhoeff_checksum(base)
    tampered = base + str((check + 1) % 10)
    assert not verhoeff_validate(tampered)
    assert not verhoeff_validate("abcd")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2,50,000", "250000"),
        ("Rs. 50,000", "50000"),
        ("2.5 lakh", "250000"),
        ("2 lakh", "200000"),
        ("1 crore", "10000000"),
        ("₹1,00,000", "100000"),
    ],
)
def test_parse_inr_amount(text: str, expected: str) -> None:
    assert parse_inr_amount(text) == Decimal(expected)


def test_parse_inr_amount_none() -> None:
    assert parse_inr_amount("no number here") is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("01/06/1990", date(1990, 6, 1)),
        ("15-04-2025", date(2025, 4, 15)),
        ("2026-03-31", date(2026, 3, 31)),
        ("1990", date(1990, 1, 1)),
    ],
)
def test_parse_date(text: str, expected: date) -> None:
    assert parse_date(text) == expected


def test_parse_date_none() -> None:
    assert parse_date("not a date") is None


def test_find_identifiers() -> None:
    assert find_pan("PAN: ABCDE1234F issued") == "ABCDE1234F"
    assert find_pan("no pan here") is None
    assert find_aadhaar("UID 1234 5678 9012 issued") == "123456789012"
    assert find_aadhaar("no aadhaar") is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Certificate No 12345 Amount Rs 50000", "50000"),
        ("Cert No: 789 Annual Income Rs. 2,50,000", "250000"),
    ],
)
def test_parse_inr_amount_anchors_to_currency(text: str, expected: str) -> None:
    assert parse_inr_amount(text) == Decimal(expected)


@pytest.mark.parametrize("text", ["Rs -5000", "-5000", "Rs. -2.5 lakh"])
def test_parse_inr_amount_rejects_negative(text: str) -> None:
    assert parse_inr_amount(text) is None


@pytest.mark.parametrize("text", ["04/13/2025", "04/30/2026", "2/30/2025"])
def test_parse_date_rejects_ambiguous_dates(text: str) -> None:
    assert parse_date(text) is None


def test_find_aadhaar_prefers_verhoeff_valid() -> None:
    base = "23456789012"
    valid = base + str(verhoeff_checksum(base))
    invalid = base + str((int(valid[-1]) + 1) % 10)
    text = (
        f"Account {invalid[:4]} {invalid[4:8]} {invalid[8:]}\n"
        f"Aadhaar {valid[:4]} {valid[4:8]} {valid[8:]}"
    )
    assert find_aadhaar(text) == valid
