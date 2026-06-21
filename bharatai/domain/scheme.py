"""bharatai.domain.scheme — Scheme aggregate plus its criteria/benefit value objects."""
from __future__ import annotations

from datetime import date

from pydantic import Field

from bharatai.domain.base import Entity, ValueObject
from bharatai.domain.enums import Category, DocumentType, Gender, IndianState, ResidenceType
from bharatai.domain.value_objects import DateRange, Money


class EligibilityCriteria(ValueObject):
    """Structured, machine-checkable eligibility rules for a scheme.

    The deterministic eligibility engine evaluates these directly; ``raw_rules_text``
    carries anything not yet structured, for an optional LLM explanation pass.
    """

    min_age: int | None = Field(default=None, ge=0, le=120)
    max_age: int | None = Field(default=None, ge=0, le=120)
    allowed_genders: list[Gender] = Field(default_factory=list)
    allowed_categories: list[Category] = Field(default_factory=list)
    max_annual_income: Money | None = None
    allowed_states: list[IndianState] = Field(default_factory=list)
    residence_types: list[ResidenceType] = Field(default_factory=list)
    requires_bpl: bool | None = None
    min_disability_percentage: int | None = Field(default=None, ge=0, le=100)
    required_documents: list[DocumentType] = Field(default_factory=list)
    raw_rules_text: str | None = None
    custom_flags: dict[str, str] = Field(default_factory=dict)


class SchemeBenefit(ValueObject):
    """A single benefit a scheme provides."""

    description: str
    amount: Money | None = None
    frequency: str | None = None  # e.g. "one-time", "annual", "monthly"


class Scheme(Entity):
    """A government scheme, with provenance fields required by the v1 trust posture."""

    name: str
    code: str | None = None
    description: str = ""
    department: str | None = None
    level: str | None = None  # "central" | "state"
    state: IndianState | None = None  # None == central / all-India
    category_tags: list[str] = Field(default_factory=list)
    eligibility_criteria: EligibilityCriteria = Field(default_factory=EligibilityCriteria)
    benefits: list[SchemeBenefit] = Field(default_factory=list)
    application_window: DateRange | None = None
    source_url: str | None = None
    verified_at: date | None = None
    is_active: bool = True
