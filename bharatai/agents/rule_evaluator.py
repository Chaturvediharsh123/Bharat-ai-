"""bharatai.agents.rule_evaluator — the deterministic eligibility rule engine.

Pure, LLM-free logic that checks a CitizenProfile against an EligibilityCriteria and
returns one CriterionCheck per applicable rule. Each check is PASS (data present and
satisfied), FAIL (data present and violated), or MISSING (data needed but absent).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.eligibility import CriterionEvaluation
from bharatai.domain.enums import DocumentType
from bharatai.domain.scheme import EligibilityCriteria

Outcome = Literal["pass", "fail", "missing"]


@dataclass(frozen=True)
class CriterionCheck:
    """A single criterion's evaluation plus its outcome and any missing profile field."""

    evaluation: CriterionEvaluation
    outcome: Outcome
    missing_field: str | None = None


def _check(
    criterion: str,
    *,
    outcome: Outcome,
    expected: str | None = None,
    actual: str | None = None,
    detail: str | None = None,
    missing_field: str | None = None,
) -> CriterionCheck:
    return CriterionCheck(
        evaluation=CriterionEvaluation(
            criterion=criterion,
            passed=outcome == "pass",
            expected=expected,
            actual=actual,
            detail=detail,
        ),
        outcome=outcome,
        missing_field=missing_field,
    )


class RuleEvaluator:
    """Evaluates a profile against structured eligibility criteria (deterministic)."""

    def evaluate(
        self,
        profile: CitizenProfile,
        criteria: EligibilityCriteria,
        validated_doc_types: list[DocumentType],
    ) -> list[CriterionCheck]:
        """Return one CriterionCheck per applicable rule in the criteria."""
        checks: list[CriterionCheck] = []
        if criteria.min_age is not None or criteria.max_age is not None:
            checks.append(self._age(profile, criteria))
        if criteria.allowed_genders:
            checks.append(self._gender(profile, criteria))
        if criteria.allowed_categories:
            checks.append(self._category(profile, criteria))
        if criteria.max_annual_income is not None:
            checks.append(self._income(profile, criteria))
        if criteria.allowed_states:
            checks.append(self._state(profile, criteria))
        if criteria.residence_types:
            checks.append(self._residence(profile, criteria))
        if criteria.requires_bpl is not None:
            checks.append(self._bpl(profile, criteria))
        if criteria.min_disability_percentage is not None:
            checks.append(self._disability(profile, criteria))
        if criteria.required_documents:
            checks.append(self._documents(criteria, validated_doc_types))
        return checks

    def _age(self, profile: CitizenProfile, criteria: EligibilityCriteria) -> CriterionCheck:
        low, high = criteria.min_age, criteria.max_age
        expected = f"{low if low is not None else 0}-{high if high is not None else 120}"
        age = profile.age
        if age is None:
            return _check(
                "age", outcome="missing", expected=expected,
                detail="date of birth not provided", missing_field="date_of_birth",
            )
        ok = (low is None or age >= low) and (high is None or age <= high)
        return _check(
            "age", outcome="pass" if ok else "fail", expected=expected, actual=str(age),
            detail=None if ok else "age is outside the allowed range",
        )

    def _gender(self, profile: CitizenProfile, criteria: EligibilityCriteria) -> CriterionCheck:
        expected = ", ".join(g.value for g in criteria.allowed_genders)
        if profile.gender is None:
            return _check("gender", outcome="missing", expected=expected, missing_field="gender")
        ok = profile.gender in criteria.allowed_genders
        return _check("gender", outcome="pass" if ok else "fail", expected=expected,
                      actual=profile.gender.value)

    def _category(self, profile: CitizenProfile, criteria: EligibilityCriteria) -> CriterionCheck:
        expected = ", ".join(c.value for c in criteria.allowed_categories)
        if profile.category is None:
            return _check(
                "category", outcome="missing", expected=expected, missing_field="category"
            )
        ok = profile.category in criteria.allowed_categories
        return _check("category", outcome="pass" if ok else "fail", expected=expected,
                      actual=profile.category.value)

    def _income(self, profile: CitizenProfile, criteria: EligibilityCriteria) -> CriterionCheck:
        cap = criteria.max_annual_income
        assert cap is not None  # guarded by caller
        expected = f"<= Rs {cap.amount}"
        if profile.annual_income is None:
            return _check("annual_income", outcome="missing", expected=expected,
                          missing_field="annual_income")
        if profile.annual_income.currency != cap.currency:
            return _check(
                "annual_income", outcome="missing", expected=expected,
                missing_field="annual_income",
                detail="income currency does not match the scheme currency",
            )
        ok = profile.annual_income.to_paise() <= cap.to_paise()
        return _check("annual_income", outcome="pass" if ok else "fail", expected=expected,
                      actual=f"Rs {profile.annual_income.amount}",
                      detail=None if ok else "income exceeds the limit")

    def _state(self, profile: CitizenProfile, criteria: EligibilityCriteria) -> CriterionCheck:
        expected = ", ".join(s.value for s in criteria.allowed_states)
        state = profile.address.state if profile.address else None
        if state is None:
            return _check("state", outcome="missing", expected=expected, missing_field="state")
        ok = state in criteria.allowed_states
        return _check(
            "state", outcome="pass" if ok else "fail", expected=expected, actual=state.value
        )

    def _residence(self, profile: CitizenProfile, criteria: EligibilityCriteria) -> CriterionCheck:
        expected = ", ".join(r.value for r in criteria.residence_types)
        residence = profile.address.residence_type if profile.address else None
        if residence is None:
            return _check("residence_type", outcome="missing", expected=expected,
                          missing_field="residence_type")
        ok = residence in criteria.residence_types
        return _check("residence_type", outcome="pass" if ok else "fail", expected=expected,
                      actual=residence.value)

    def _bpl(self, profile: CitizenProfile, criteria: EligibilityCriteria) -> CriterionCheck:
        expected = str(criteria.requires_bpl)
        if profile.is_bpl is None:
            return _check("bpl", outcome="missing", expected=expected, missing_field="is_bpl")
        ok = profile.is_bpl == criteria.requires_bpl
        return _check("bpl", outcome="pass" if ok else "fail", expected=expected,
                      actual=str(profile.is_bpl))

    def _disability(self, profile: CitizenProfile, criteria: EligibilityCriteria) -> CriterionCheck:
        minimum = criteria.min_disability_percentage
        assert minimum is not None  # guarded by caller
        expected = f">= {minimum}%"
        percentage = profile.disability_percentage
        if percentage is None and profile.disability_status:
            return _check("disability_percentage", outcome="missing", expected=expected,
                          missing_field="disability_percentage")
        actual = percentage if percentage is not None else 0
        ok = actual >= minimum
        return _check("disability_percentage", outcome="pass" if ok else "fail", expected=expected,
                      actual=f"{actual}%")

    def _documents(
        self, criteria: EligibilityCriteria, validated: list[DocumentType]
    ) -> CriterionCheck:
        expected = ", ".join(d.value for d in criteria.required_documents)
        missing = [d for d in criteria.required_documents if d not in validated]
        if missing:
            return _check(
                "required_documents", outcome="missing", expected=expected,
                actual=", ".join(d.value for d in validated) or "none",
                detail="missing/unverified: " + ", ".join(d.value for d in missing),
                missing_field="documents",
            )
        return _check("required_documents", outcome="pass", expected=expected,
                      actual=", ".join(d.value for d in validated))
