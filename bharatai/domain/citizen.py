"""bharatai.domain.citizen — the CitizenProfile aggregate."""
from __future__ import annotations

from datetime import date

from pydantic import Field, field_validator

from bharatai.domain.base import Entity
from bharatai.domain.enums import Category, Gender, MaritalStatus
from bharatai.domain.value_objects import Address, Money


class CitizenProfile(Entity):
    """A citizen's self-reported profile, built incrementally (most fields optional)."""

    full_name: str | None = None
    date_of_birth: date | None = None
    gender: Gender | None = None
    category: Category | None = None
    marital_status: MaritalStatus | None = None
    annual_income: Money | None = None
    occupation: str | None = None
    is_bpl: bool | None = None
    disability_status: bool = False
    disability_percentage: int | None = Field(default=None, ge=0, le=100)
    family_size: int | None = Field(default=None, ge=1)
    address: Address | None = None
    aadhaar_last4: str | None = None
    pan_masked: str | None = None
    mobile: str | None = None
    languages: list[str] = Field(default_factory=list)

    @field_validator("aadhaar_last4")
    @classmethod
    def _validate_last4(cls, value: str | None) -> str | None:
        """Aadhaar is stored as last-4 only; reject anything else."""
        if value is None:
            return None
        if not (value.isdigit() and len(value) == 4):
            raise ValueError("aadhaar_last4 must be exactly 4 digits")
        return value

    @property
    def age(self) -> int | None:
        """Age in completed years, derived from date_of_birth (None if unknown)."""
        if self.date_of_birth is None:
            return None
        today = date.today()
        years = today.year - self.date_of_birth.year
        if (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day):
            years -= 1
        return years
