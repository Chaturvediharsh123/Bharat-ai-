"""bharatai.domain.eligibility — EligibilityResult and per-rule explanation."""
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from bharatai.domain.base import Entity, ValueObject
from bharatai.domain.enums import EligibilityStatus


class CriterionEvaluation(ValueObject):
    """The outcome of checking one eligibility criterion (drives explainability)."""

    criterion: str
    passed: bool
    expected: str | None = None
    actual: str | None = None
    detail: str | None = None


class EligibilityResult(Entity):
    """A deterministic, explainable eligibility decision for one citizen + scheme."""

    citizen_id: str
    scheme_id: str
    status: EligibilityStatus = EligibilityStatus.PENDING
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evaluations: list[CriterionEvaluation] = Field(default_factory=list)
    missing_profile_fields: list[str] = Field(default_factory=list)
    explanation: str | None = None
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
