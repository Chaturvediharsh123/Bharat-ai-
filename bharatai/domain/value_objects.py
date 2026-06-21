"""bharatai.domain.value_objects — immutable, equality-by-value building blocks.

Money is modelled as a ``Decimal`` (rupees) to avoid binary-float drift; the
database layer stores it as integer paise. Conversion helpers live here so they
are reusable without importing any persistence code.
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import Field, field_validator, model_validator

from bharatai.domain.base import ValueObject
from bharatai.domain.enums import IndianState, ResidenceType

_PAISE = Decimal(100)


class Money(ValueObject):
    """A non-negative monetary amount in Indian Rupees (stored as paise in the DB)."""

    amount: Decimal = Field(ge=Decimal(0))
    currency: str = "INR"

    @field_validator("amount")
    @classmethod
    def _quantize(cls, value: Decimal) -> Decimal:
        """Round to two decimal places (paise precision)."""
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def to_paise(self) -> int:
        """Return the amount as an integer number of paise."""
        return int((self.amount * _PAISE).to_integral_value(rounding=ROUND_HALF_UP))

    @classmethod
    def from_paise(cls, paise: int, currency: str = "INR") -> Money:
        """Build a Money from an integer number of paise."""
        return cls(amount=Decimal(paise) / _PAISE, currency=currency)

    @classmethod
    def zero(cls) -> Money:
        """Return ₹0.00."""
        return cls(amount=Decimal(0))


class Address(ValueObject):
    """A postal address. ``state``/``district`` drive scheme targeting + DB indexes."""

    line: str | None = None
    village_or_city: str | None = None
    district: str | None = None
    state: IndianState | None = None
    pincode: str | None = None
    residence_type: ResidenceType | None = None

    @field_validator("pincode")
    @classmethod
    def _validate_pincode(cls, value: str | None) -> str | None:
        """Ensure a 6-digit Indian PIN code when provided."""
        if value is None:
            return None
        if not (value.isdigit() and len(value) == 6):
            raise ValueError("pincode must be exactly 6 digits")
        return value


class DateRange(ValueObject):
    """An inclusive date window (e.g. a scheme's application window)."""

    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def _check_order(self) -> DateRange:
        """Reject ranges where start is after end."""
        if self.start and self.end and self.start > self.end:
            raise ValueError("DateRange.start must not be after end")
        return self

    def contains(self, day: date) -> bool:
        """Return True if ``day`` falls within the (possibly open-ended) range."""
        if self.start and day < self.start:
            return False
        if self.end and day > self.end:
            return False
        return True


class OcrField(ValueObject):
    """A single key/value pair extracted from a document by OCR."""

    name: str
    value: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    bbox: tuple[float, float, float, float] | None = None


class OcrResult(ValueObject):
    """The canonical output of the OCR layer (the only OCR-shaped domain object)."""

    raw_text: str = ""
    fields: list[OcrField] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    engine: str = "paddleocr"
    language: str = "en"
