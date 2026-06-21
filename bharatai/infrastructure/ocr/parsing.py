"""bharatai.infrastructure.ocr.parsing — pure parsing helpers for Indian documents.

All functions here are deterministic and dependency-free (no OCR engine), so the
high-risk logic — Aadhaar Verhoeff checksum, Indian numeral money parsing, date and
identifier extraction — is exhaustively unit-testable.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# ── Verhoeff checksum (Aadhaar) ──────────────────────────────────────────────
_MULT = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_PERM = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)
_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)

_AADHAAR_RE = re.compile(r"\b(\d{4})\s?(\d{4})\s?(\d{4})\b")
_PAN_RE = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y")

_NUM = r"(-?\s*[0-9]+(?:\.[0-9]+)?)"
_UNIT = r"(lakhs?|lacs?|crores?|cr)"
# Amount-matching, in priority order: anchored to a currency token, then to a
# lakh/crore unit, then a bare number — so a leading serial number is not misread.
_AMOUNT_PATTERNS = (
    re.compile(rf"(?:rs\.?|inr|₹)\s*{_NUM}\s*{_UNIT}?"),
    re.compile(rf"{_NUM}\s*{_UNIT}\b"),
    re.compile(rf"{_NUM}()"),
)


def verhoeff_checksum(number: str) -> int:
    """Return the Verhoeff check digit for a string of digits (excluding the check digit)."""
    check = 0
    for position, item in enumerate(reversed(number)):
        check = _MULT[check][_PERM[(position + 1) % 8][int(item)]]
    return _INV[check]


def verhoeff_validate(number: str) -> bool:
    """Return True if a full numeric string (including its check digit) is Verhoeff-valid."""
    if not number.isdigit():
        return False
    check = 0
    for position, item in enumerate(reversed(number)):
        check = _MULT[check][_PERM[position % 8][int(item)]]
    return check == 0


def find_aadhaar(text: str) -> str | None:
    """Return the first Verhoeff-valid 12-digit candidate, else the first match, or None."""
    candidates = ["".join(match.groups()) for match in _AADHAAR_RE.finditer(text)]
    if not candidates:
        return None
    for candidate in candidates:
        if verhoeff_validate(candidate):
            return candidate
    return candidates[0]


def find_pan(text: str) -> str | None:
    """Return the first PAN (ABCDE1234F) found in upper-cased text, or None."""
    match = _PAN_RE.search(text.upper())
    return match.group(1) if match else None


def parse_inr_amount(text: str) -> Decimal | None:
    """Parse an Indian-rupee amount, handling commas and lakh/crore units.

    Examples: '2,50,000' -> 250000, 'Rs. 2.5 lakh' -> 250000, '1 crore' -> 10000000.
    """
    cleaned = text.lower().replace(",", "")
    match = None
    for pattern in _AMOUNT_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            break
    if not match:
        return None
    try:
        value = Decimal(match.group(1).replace(" ", ""))
    except InvalidOperation:
        return None
    unit = match.group(2)
    if unit and unit.startswith(("lakh", "lac")):
        value *= Decimal(100_000)
    elif unit and unit.startswith(("crore", "cr")):
        value *= Decimal(10_000_000)
    return value if value >= 0 else None


def parse_date(text: str) -> date | None:
    """Parse a date in common Indian formats; falls back to a bare 4-digit year."""
    candidate = text.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(candidate, fmt).date()  # noqa: DTZ007 - date only
        except ValueError:
            continue
    # A full day/month/year token that failed strict parsing is ambiguous/invalid
    # (e.g. US-style 04/13/2025): do not fabricate a January-1 date from its year.
    if re.search(r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}", candidate):
        return None
    year_match = re.search(r"\b(19|20)\d{2}\b", candidate)
    if year_match:
        return date(int(year_match.group(0)), 1, 1)
    return None
