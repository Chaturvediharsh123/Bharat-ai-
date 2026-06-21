"""Tests for the RecommendationAgent (lost/missed benefits, qualitative, no rupee figure)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from bharatai.agents.base import AgentContext
from bharatai.agents.recommendation_agent import RecommendationAgent, RecommendationInput
from bharatai.domain.application import ApplicationHistoryEntry
from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.eligibility import EligibilityResult
from bharatai.domain.enums import ApplicationStatus, EligibilityStatus
from bharatai.domain.scheme import Scheme
from bharatai.domain.value_objects import DateRange

_CTX = AgentContext(trace_id="trace-1")
_AGENT = RecommendationAgent()


def _scheme(name: str, window_end: date | None = None) -> Scheme:
    window = DateRange(end=window_end) if window_end else None
    return Scheme(name=name, application_window=window)


def _elig(
    scheme_id: str,
    status: EligibilityStatus,
    confidence: float = 0.9,
    missing: list[str] | None = None,
    evaluated_at: datetime | None = None,
) -> EligibilityResult:
    return EligibilityResult(
        citizen_id="c",
        scheme_id=scheme_id,
        status=status,
        confidence=confidence,
        missing_profile_fields=missing or [],
        evaluated_at=evaluated_at or datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_recommends_eligible_not_applied() -> None:
    kisan, pmay = _scheme("PM-KISAN"), _scheme("PMAY")
    result = _AGENT.run(
        RecommendationInput(
            profile=CitizenProfile(),
            schemes=[kisan, pmay],
            eligibility_results=[
                _elig(kisan.id, EligibilityStatus.ELIGIBLE),
                _elig(pmay.id, EligibilityStatus.ELIGIBLE),
            ],
            applications=[
                ApplicationHistoryEntry(
                    citizen_id="c", scheme_id=pmay.id, status=ApplicationStatus.SUBMITTED
                )
            ],
        ),
        _CTX,
    )
    assert [r.scheme_name for r in result.recommendations] == ["PM-KISAN"]
    assert result.recommendations[0].status_hint == "eligible"


def test_potential_for_needs_more_info() -> None:
    scheme = _scheme("Scholarship")
    [rec] = _AGENT.run(
        RecommendationInput(
            profile=CitizenProfile(),
            schemes=[scheme],
            eligibility_results=[
                _elig(scheme.id, EligibilityStatus.NEEDS_MORE_INFO, missing=["annual_income"])
            ],
        ),
        _CTX,
    ).recommendations
    assert rec.status_hint == "potential"
    assert rec.priority == "low"
    assert "annual_income" in rec.reason


def test_no_rupee_figure_in_output() -> None:
    scheme = _scheme("PM-KISAN")
    result = _AGENT.run(
        RecommendationInput(
            profile=CitizenProfile(),
            schemes=[scheme],
            eligibility_results=[_elig(scheme.id, EligibilityStatus.ELIGIBLE)],
        ),
        _CTX,
    )
    blob = (result.summary + " " + " ".join(r.reason for r in result.recommendations)).lower()
    assert "₹" not in blob
    assert "rs" not in blob
    assert "lakh" not in blob
    assert "crore" not in blob


def test_ranking_orders_eligible_high_first() -> None:
    today = _CTX.now.date()
    soon = _scheme("Soon", window_end=today)  # near deadline -> high priority
    later = _scheme("Later")  # no deadline, low confidence -> medium
    potential = _scheme("Potential")
    result = _AGENT.run(
        RecommendationInput(
            profile=CitizenProfile(),
            schemes=[soon, later, potential],
            eligibility_results=[
                _elig(later.id, EligibilityStatus.ELIGIBLE, confidence=0.5),
                _elig(soon.id, EligibilityStatus.ELIGIBLE, confidence=0.5),
                _elig(potential.id, EligibilityStatus.NEEDS_MORE_INFO),
            ],
        ),
        _CTX,
    )
    assert [r.scheme_name for r in result.recommendations] == ["Soon", "Later", "Potential"]


def test_excludes_approved_application() -> None:
    scheme = _scheme("PMAY")
    result = _AGENT.run(
        RecommendationInput(
            profile=CitizenProfile(),
            schemes=[scheme],
            eligibility_results=[_elig(scheme.id, EligibilityStatus.ELIGIBLE)],
            applications=[
                ApplicationHistoryEntry(
                    citizen_id="c", scheme_id=scheme.id, status=ApplicationStatus.APPROVED
                )
            ],
        ),
        _CTX,
    )
    assert result.recommendations == []


def test_top_k_limit() -> None:
    schemes = [_scheme(f"S{i}") for i in range(5)]
    result = _AGENT.run(
        RecommendationInput(
            profile=CitizenProfile(),
            schemes=schemes,
            eligibility_results=[_elig(s.id, EligibilityStatus.ELIGIBLE) for s in schemes],
            top_k=3,
        ),
        _CTX,
    )
    assert len(result.recommendations) == 3


def test_latest_status_governs_over_stale_history() -> None:
    scheme = _scheme("PM-KISAN")
    # Append-only history: an older ELIGIBLE row plus a newer NOT_ELIGIBLE row.
    older = _elig(
        scheme.id, EligibilityStatus.ELIGIBLE, evaluated_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    newer = _elig(
        scheme.id,
        EligibilityStatus.NOT_ELIGIBLE,
        evaluated_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    result = _AGENT.run(
        RecommendationInput(
            profile=CitizenProfile(), schemes=[scheme], eligibility_results=[newer, older]
        ),
        _CTX,
    )
    assert result.recommendations == []  # newest NOT_ELIGIBLE wins; no duplicate, no stale leak


def test_live_deadline_outranks_expired() -> None:
    today = _CTX.now.date()
    expired = _scheme("AAA-expired", window_end=today - timedelta(days=30))
    live = _scheme("ZZZ-live", window_end=today + timedelta(days=10))
    result = _AGENT.run(
        RecommendationInput(
            profile=CitizenProfile(),
            schemes=[expired, live],
            eligibility_results=[
                _elig(expired.id, EligibilityStatus.ELIGIBLE),
                _elig(live.id, EligibilityStatus.ELIGIBLE),
            ],
        ),
        _CTX,
    )
    # Despite the alphabetical name advantage of the expired scheme, the live one ranks first.
    assert [r.scheme_name for r in result.recommendations] == ["ZZZ-live", "AAA-expired"]


def test_empty_recommends_nothing() -> None:
    result = _AGENT.run(
        RecommendationInput(profile=CitizenProfile(), schemes=[], eligibility_results=[]), _CTX
    )
    assert result.recommendations == []
    assert "advisory" in result.summary.lower()
