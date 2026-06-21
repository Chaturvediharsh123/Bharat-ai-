"""Tests for the deterministic eligibility rule engine."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from bharatai.agents.rule_evaluator import RuleEvaluator
from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.enums import Category, DocumentType, Gender, IndianState, ResidenceType
from bharatai.domain.scheme import EligibilityCriteria
from bharatai.domain.value_objects import Address, Money

_EVAL = RuleEvaluator()


def test_age_missing_without_dob() -> None:
    checks = _EVAL.evaluate(CitizenProfile(), EligibilityCriteria(min_age=18), [])
    assert checks[0].outcome == "missing"
    assert checks[0].missing_field == "date_of_birth"


def test_age_pass_and_fail() -> None:
    criteria = EligibilityCriteria(min_age=18, max_age=60)
    adult = CitizenProfile(date_of_birth=date(1990, 1, 1))
    assert _EVAL.evaluate(adult, criteria, [])[0].outcome == "pass"
    child = CitizenProfile(date_of_birth=date(2020, 1, 1))
    assert _EVAL.evaluate(child, criteria, [])[0].outcome == "fail"


def test_income_pass_and_fail() -> None:
    criteria = EligibilityCriteria(max_annual_income=Money(amount=Decimal("100000")))
    under = CitizenProfile(annual_income=Money(amount=Decimal("50000")))
    over = CitizenProfile(annual_income=Money(amount=Decimal("150000")))
    assert _EVAL.evaluate(under, criteria, [])[0].outcome == "pass"
    assert _EVAL.evaluate(over, criteria, [])[0].outcome == "fail"


def test_income_currency_mismatch_is_missing() -> None:
    criteria = EligibilityCriteria(max_annual_income=Money(amount=Decimal("100000")))
    profile = CitizenProfile(annual_income=Money(amount=Decimal("1"), currency="USD"))
    check = _EVAL.evaluate(profile, criteria, [])[0]
    assert check.outcome == "missing"  # not comparable -> not a confident pass/fail
    assert check.missing_field == "annual_income"


def test_category_check() -> None:
    criteria = EligibilityCriteria(allowed_categories=[Category.SC, Category.ST])
    sc = _EVAL.evaluate(CitizenProfile(category=Category.SC), criteria, [])
    assert sc[0].outcome == "pass"
    general = _EVAL.evaluate(CitizenProfile(category=Category.GENERAL), criteria, [])
    assert general[0].outcome == "fail"


def test_disability_logic() -> None:
    criteria = EligibilityCriteria(min_disability_percentage=40)
    not_disabled = _EVAL.evaluate(CitizenProfile(disability_status=False), criteria, [])
    assert not_disabled[0].outcome == "fail"  # treated as 0%
    unknown_pct = _EVAL.evaluate(CitizenProfile(disability_status=True), criteria, [])
    assert unknown_pct[0].outcome == "missing"
    enough = _EVAL.evaluate(CitizenProfile(disability_percentage=50), criteria, [])
    assert enough[0].outcome == "pass"


def test_gender_check() -> None:
    criteria = EligibilityCriteria(allowed_genders=[Gender.FEMALE])
    assert _EVAL.evaluate(CitizenProfile(gender=Gender.FEMALE), criteria, [])[0].outcome == "pass"
    assert _EVAL.evaluate(CitizenProfile(gender=Gender.MALE), criteria, [])[0].outcome == "fail"
    assert _EVAL.evaluate(CitizenProfile(), criteria, [])[0].outcome == "missing"


def test_state_and_residence_checks() -> None:
    state_criteria = EligibilityCriteria(allowed_states=[IndianState.RAJASTHAN])
    raj = CitizenProfile(address=Address(state=IndianState.RAJASTHAN))
    assert _EVAL.evaluate(raj, state_criteria, [])[0].outcome == "pass"
    kerala = CitizenProfile(address=Address(state=IndianState.KERALA))
    assert _EVAL.evaluate(kerala, state_criteria, [])[0].outcome == "fail"
    assert _EVAL.evaluate(CitizenProfile(), state_criteria, [])[0].outcome == "missing"

    res_criteria = EligibilityCriteria(residence_types=[ResidenceType.RURAL])
    rural = CitizenProfile(address=Address(residence_type=ResidenceType.RURAL))
    assert _EVAL.evaluate(rural, res_criteria, [])[0].outcome == "pass"
    assert _EVAL.evaluate(CitizenProfile(), res_criteria, [])[0].outcome == "missing"


def test_bpl_check() -> None:
    criteria = EligibilityCriteria(requires_bpl=True)
    assert _EVAL.evaluate(CitizenProfile(is_bpl=True), criteria, [])[0].outcome == "pass"
    assert _EVAL.evaluate(CitizenProfile(is_bpl=False), criteria, [])[0].outcome == "fail"
    assert _EVAL.evaluate(CitizenProfile(), criteria, [])[0].outcome == "missing"


def test_age_max_bound() -> None:
    from datetime import date

    criteria = EligibilityCriteria(max_age=60)
    young = CitizenProfile(date_of_birth=date(1990, 1, 1))
    assert _EVAL.evaluate(young, criteria, [])[0].outcome == "pass"


def test_required_documents() -> None:
    criteria = EligibilityCriteria(required_documents=[DocumentType.AADHAAR, DocumentType.INCOME])
    missing = _EVAL.evaluate(CitizenProfile(), criteria, [DocumentType.AADHAAR])
    assert missing[0].outcome == "missing"
    complete = _EVAL.evaluate(
        CitizenProfile(), criteria, [DocumentType.AADHAAR, DocumentType.INCOME]
    )
    assert complete[0].outcome == "pass"
