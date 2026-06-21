"""Tests for the EligibilityIntelligenceAgent (deterministic core + LLM-only explanation)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from bharatai.agents.base import AgentContext
from bharatai.agents.eligibility_agent import EligibilityInput, EligibilityIntelligenceAgent
from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.enums import Category, DocumentType, EligibilityStatus
from bharatai.domain.scheme import EligibilityCriteria, Scheme
from bharatai.domain.value_objects import Money
from tests.fakes.fake_llm import FakeLLM

_CTX = AgentContext(trace_id="trace-1")
_AGENT = EligibilityIntelligenceAgent()


def _scheme(criteria: EligibilityCriteria, name: str = "Test Scheme") -> Scheme:
    return Scheme(name=name, source_url="https://example.gov.in", eligibility_criteria=criteria)


def test_eligible_when_all_criteria_pass() -> None:
    criteria = EligibilityCriteria(
        min_age=18,
        max_age=60,
        allowed_categories=[Category.OBC],
        max_annual_income=Money(amount=Decimal("200000")),
    )
    profile = CitizenProfile(
        date_of_birth=date(1990, 1, 1),
        category=Category.OBC,
        annual_income=Money(amount=Decimal("150000")),
    )
    [result] = _AGENT.run(EligibilityInput(profile=profile, schemes=[_scheme(criteria)]), _CTX)
    assert result.status is EligibilityStatus.ELIGIBLE
    assert result.score == 1.0
    assert result.confidence == 1.0
    assert result.missing_profile_fields == []
    assert "advisory" in (result.explanation or "").lower()


def test_not_eligible_when_income_over_cap() -> None:
    criteria = EligibilityCriteria(max_annual_income=Money(amount=Decimal("100000")))
    profile = CitizenProfile(annual_income=Money(amount=Decimal("250000")))
    [result] = _AGENT.run(EligibilityInput(profile=profile, schemes=[_scheme(criteria)]), _CTX)
    assert result.status is EligibilityStatus.NOT_ELIGIBLE
    assert result.score < 1.0


def test_needs_more_info_when_field_missing() -> None:
    criteria = EligibilityCriteria(
        max_annual_income=Money(amount=Decimal("200000")), allowed_categories=[Category.SC]
    )
    profile = CitizenProfile(category=Category.SC)  # income unknown
    [result] = _AGENT.run(EligibilityInput(profile=profile, schemes=[_scheme(criteria)]), _CTX)
    assert result.status is EligibilityStatus.NEEDS_MORE_INFO
    assert "annual_income" in result.missing_profile_fields
    assert result.confidence < 1.0


def test_required_documents_missing_needs_info() -> None:
    criteria = EligibilityCriteria(required_documents=[DocumentType.AADHAAR, DocumentType.INCOME])
    result = _AGENT.run(
        EligibilityInput(
            profile=CitizenProfile(),
            schemes=[_scheme(criteria)],
            validated_doc_types=[DocumentType.AADHAAR],
        ),
        _CTX,
    )[0]
    assert result.status is EligibilityStatus.NEEDS_MORE_INFO
    assert "documents" in result.missing_profile_fields


def test_no_criteria_is_eligible_low_confidence() -> None:
    [result] = _AGENT.run(
        EligibilityInput(profile=CitizenProfile(), schemes=[_scheme(EligibilityCriteria())]), _CTX
    )
    assert result.status is EligibilityStatus.ELIGIBLE
    assert result.confidence == 0.5


def test_llm_explains_but_never_changes_decision() -> None:
    criteria = EligibilityCriteria(
        max_annual_income=Money(amount=Decimal("100000")),
        raw_rules_text="Applicant must be a resident farmer.",
    )
    profile = CitizenProfile(annual_income=Money(amount=Decimal("250000")))  # over cap
    llm = FakeLLM("You qualify for everything!")  # adversarial / wrong text
    agent = EligibilityIntelligenceAgent(llm=llm)
    [result] = agent.run(EligibilityInput(profile=profile, schemes=[_scheme(criteria)]), _CTX)
    assert result.status is EligibilityStatus.NOT_ELIGIBLE  # LLM did not change the decision
    assert (result.explanation or "").startswith("You qualify for everything!")
    # advisory disclaimer + source are enforced in code, not delegated to the LLM
    assert "advisory only" in (result.explanation or "")
    assert "https://example.gov.in" in (result.explanation or "")
    assert len(llm.calls) == 1


def test_evaluates_multiple_schemes() -> None:
    generous = _scheme(EligibilityCriteria(max_annual_income=Money(amount=Decimal("300000"))), "A")
    strict = _scheme(EligibilityCriteria(max_annual_income=Money(amount=Decimal("100000"))), "B")
    profile = CitizenProfile(annual_income=Money(amount=Decimal("200000")))
    results = _AGENT.run(EligibilityInput(profile=profile, schemes=[generous, strict]), _CTX)
    assert [r.status for r in results] == [
        EligibilityStatus.ELIGIBLE,
        EligibilityStatus.NOT_ELIGIBLE,
    ]
