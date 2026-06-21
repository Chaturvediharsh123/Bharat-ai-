"""bharatai.agents.recommendation_agent — (6) detect lost / missed benefits.

Surfaces schemes a citizen appears eligible for (or could qualify for) but is NOT currently
availing, ranked qualitatively. Per the v1 trust posture this is purely advisory and
deliberately carries NO rupee 'lost benefit' figure — only 'schemes you may have missed'.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from bharatai.agents.base import AgentContext, BaseAgent
from bharatai.common.logging import get_logger
from bharatai.domain.application import ApplicationHistoryEntry
from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.eligibility import EligibilityResult
from bharatai.domain.enums import ApplicationStatus, EligibilityStatus
from bharatai.domain.scheme import Scheme

_AVAILING = {
    ApplicationStatus.SUBMITTED,
    ApplicationStatus.UNDER_REVIEW,
    ApplicationStatus.APPROVED,
}
_DEADLINE_SOON_DAYS = 30
_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

StatusHint = Literal["eligible", "potential"]
Priority = Literal["high", "medium", "low"]


class Recommendation(BaseModel):
    """A single missed-benefit recommendation (qualitative, no monetary value)."""

    model_config = ConfigDict(extra="forbid")

    scheme_id: str
    scheme_name: str
    status_hint: StatusHint
    priority: Priority
    reason: str
    application_deadline: date | None = None
 

class RecommendationInput(BaseModel):
    """Inputs: the profile, prior eligibility results, the schemes, and applications."""

    model_config = ConfigDict(extra="forbid")

    profile: CitizenProfile
    eligibility_results: list[EligibilityResult]
    schemes: list[Scheme]
    applications: list[ApplicationHistoryEntry] = Field(default_factory=list)
    top_k: int = 10


class RecommendationResult(BaseModel):
    """The ranked recommendations and an advisory, non-monetary summary."""

    model_config = ConfigDict(extra="forbid")

    recommendations: list[Recommendation]
    summary: str


class RecommendationAgent(BaseAgent[RecommendationInput, RecommendationResult]):
    """Detects eligible-but-unavailed schemes and ranks them (advisory, qualitative)."""

    name = "recommendation"

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Inject a logger (the agent is otherwise pure domain logic)."""
        self._logger = logger or get_logger(__name__)

    def run(self, data: RecommendationInput, ctx: AgentContext) -> RecommendationResult:
        """Return ranked schemes the citizen may be missing (no rupee figure)."""
        today = ctx.now.date()
        schemes_by_id = {scheme.id: scheme for scheme in data.schemes}
        availing = {
            app.scheme_id for app in data.applications if app.status in _AVAILING
        }

        # Keep only the latest result per scheme so a stale older row cannot resurface a
        # scheme whose current (newest) status is NOT_ELIGIBLE (eligibility history is append-only).
        latest_by_scheme: dict[str, EligibilityResult] = {}
        for result in sorted(data.eligibility_results, key=lambda r: (r.evaluated_at, r.id)):
            latest_by_scheme[result.scheme_id] = result

        recommendations: list[Recommendation] = []
        for result in latest_by_scheme.values():
            if result.status not in (
                EligibilityStatus.ELIGIBLE,
                EligibilityStatus.NEEDS_MORE_INFO,
            ):
                continue
            if result.scheme_id in availing:
                continue
            scheme = schemes_by_id.get(result.scheme_id)
            if scheme is None:
                continue
            recommendations.append(self._build(result, scheme, today))

        recommendations.sort(key=lambda rec: self._sort_key(rec, today))
        recommendations = recommendations[: data.top_k]
        self._logger.info(
            "built recommendations",
            extra={"trace_id": ctx.trace_id, "count": len(recommendations)},
        )
        return RecommendationResult(
            recommendations=recommendations, summary=self._summary(recommendations)
        )

    def _build(self, result: EligibilityResult, scheme: Scheme, today: date) -> Recommendation:
        deadline = scheme.application_window.end if scheme.application_window else None
        if result.status is EligibilityStatus.ELIGIBLE:
            return Recommendation(
                scheme_id=scheme.id,
                scheme_name=scheme.name,
                status_hint="eligible",
                priority=self._eligible_priority(result, deadline, today),
                reason=f"You appear eligible for {scheme.name} but have not applied yet.",
                application_deadline=deadline,
            )
        missing = ", ".join(result.missing_profile_fields) or "a few more details"
        return Recommendation(
            scheme_id=scheme.id,
            scheme_name=scheme.name,
            status_hint="potential",
            priority="low",
            reason=f"You may be eligible for {scheme.name}. Add {missing} to confirm.",
            application_deadline=deadline,
        )

    @staticmethod
    def _eligible_priority(
        result: EligibilityResult, deadline: date | None, today: date
    ) -> Priority:
        soon = deadline is not None and today <= deadline <= today + timedelta(
            days=_DEADLINE_SOON_DAYS
        )
        if soon or result.confidence >= 0.8:
            return "high"
        return "medium"

    @staticmethod
    def _sort_key(rec: Recommendation, today: date) -> tuple[int, int, date, str]:
        deadline = rec.application_deadline
        # A future deadline is more urgent; a missing or already-passed one sorts to the back.
        effective = deadline if (deadline is not None and deadline >= today) else date.max
        return (
            0 if rec.status_hint == "eligible" else 1,
            _PRIORITY_ORDER[rec.priority],
            effective,
            rec.scheme_name,
        )

    @staticmethod
    def _summary(recommendations: list[Recommendation]) -> str:
        if not recommendations:
            return (
                "We did not find additional schemes you may be missing based on your profile. "
                "This is advisory only; please verify on the official scheme portals."
            )
        eligible = sum(1 for rec in recommendations if rec.status_hint == "eligible")
        potential = len(recommendations) - eligible
        parts = [f"You may be missing {eligible} scheme(s) you appear eligible for"]
        if potential:
            parts.append(f" and {potential} more you could qualify for with a bit more information")
        parts.append(". This is advisory only; please verify each on the official scheme portal.")
        return "".join(parts)
