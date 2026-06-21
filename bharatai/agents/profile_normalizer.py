"""bharatai.agents.profile_normalizer — pure coercion of raw fields to domain types.

Turns messy UI/OCR scalar values (strings, numbers) into validated domain types,
returning None when a value cannot be confidently interpreted (the agent then warns).
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, TypeVar

from bharatai.domain.enums import (
    Category,
    Gender,
    IndianState,
    MaritalStatus,
    ResidenceType,
)
from bharatai.domain.value_objects import Money

_E = TypeVar("_E", bound=Enum)
_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y")
_TRUE = {"true", "yes", "y", "1", "t"}
_FALSE = {"false", "no", "n", "0", "f"}


def _coerce_enum(enum_cls: type[_E], value: Any) -> _E | None:
    if value is None:
        return None
    if isinstance(value, enum_cls):
        return value
    text = str(value).strip()
    if not text:
        return None
    for member in enum_cls:
        if str(member.value).lower() == text.lower():
            return member
    key = text.upper().replace(" ", "_").replace("-", "_")
    try:
        return enum_cls[key]
    except KeyError:
        return None


class ProfileNormalizer:
    """Coerces raw scalar inputs into domain enums, dates, money, and primitives."""

    def coerce_gender(self, value: Any) -> Gender | None:
        """Coerce a value to a Gender, or None."""
        return _coerce_enum(Gender, value)

    def coerce_category(self, value: Any) -> Category | None:
        """Coerce a value to a Category, or None."""
        return _coerce_enum(Category, value)

    def coerce_marital_status(self, value: Any) -> MaritalStatus | None:
        """Coerce a value to a MaritalStatus, or None."""
        return _coerce_enum(MaritalStatus, value)

    def coerce_state(self, value: Any) -> IndianState | None:
        """Coerce a value (state name or ISO code) to an IndianState, or None."""
        return _coerce_enum(IndianState, value)

    def coerce_residence(self, value: Any) -> ResidenceType | None:
        """Coerce a value to a ResidenceType, or None."""
        return _coerce_enum(ResidenceType, value)

    def coerce_date(self, value: Any) -> date | None:
        """Coerce a date or common date-string into a date, or None (never fabricated)."""
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value).strip()
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(text, fmt).date()  # noqa: DTZ007 - date only
            except ValueError:
                continue
        return None

    def coerce_money(self, value: Any) -> Money | None:
        """Coerce a number/string into non-negative, finite Money, or None."""
        if isinstance(value, Money):
            return value
        if isinstance(value, (int, float, Decimal)):
            text = str(value)
        else:
            text = re.sub(r"(?i)(rs\.?|inr|₹|,|\s)", "", str(value))
        try:
            amount = Decimal(text)
        except InvalidOperation:
            return None
        # Reject NaN/Infinity (Decimal parses them) and negatives before constructing Money.
        if not amount.is_finite() or amount < 0:
            return None
        return Money(amount=amount)

    def coerce_bool(self, value: Any) -> bool | None:
        """Coerce a truthy/falsy value into a bool, or None."""
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
        return None

    def coerce_int_in_range(self, value: Any, low: int, high: int) -> int | None:
        """Coerce a value to an int within [low, high], or None."""
        try:
            number = int(str(value).strip())
        except (ValueError, TypeError):
            return None
        return number if low <= number <= high else None

    def coerce_mobile(self, value: Any) -> str | None:
        """Coerce to a 10-digit Indian mobile number, stripping a +91 or 0 prefix, else None."""
        digits = re.sub(r"\D", "", str(value))
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]
        return digits if len(digits) == 10 else None

    def coerce_languages(self, value: Any) -> list[str]:
        """Coerce a list or delimited string into a list of language strings."""
        if isinstance(value, (list, tuple)):
            items = [str(item).strip() for item in value]
        else:
            items = [part.strip() for part in re.split(r"[,;]", str(value))]
        return [item for item in items if item]
