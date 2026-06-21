"""bharatai.agents.eligibility_agent — (2) deterministic eligibility evaluation.

Evaluates a CitizenProfile against one or more Schemes using a 100% deterministic rule
engine, producing an explainable EligibilityResult per scheme. The LLM (if injected) is
used ONLY to phrase a plain-language explanation — it never changes the decision.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field

from bharatai.agents.base import AgentContext, BaseAgent
from bharatai.agents.rule_evaluator import CriterionCheck, RuleEvaluator
from bharatai.application.ports.llm import LLMPort
from bharatai.common.logging import get_logger
from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.eligibility import EligibilityResult
from bharatai.domain.enums import DocumentType, EligibilityStatus
from bharatai.domain.scheme import Scheme

EXPLAIN_SYSTEM = (
    "You explain a pre-computed government-scheme eligibility decision in plain, advisory "
    "language for an Indian citizen. Do NOT change the decision or invent rules. Keep all "
    "numbers, thresholds, and dates exactly as given. Keep it to 2-3 sentences."
)


class EligibilityInput(BaseModel):
    """Input: a profile, the schemes to evaluate, and which documents are already valid."""

    model_config = ConfigDict(extra="forbid")

    profile: CitizenProfile
    schemes: list[Scheme]
    validated_doc_types: list[DocumentType] = Field(default_factory=list)
    use_llm_fallback: bool = True


class EligibilityIntelligenceAgent(BaseAgent[EligibilityInput, list[EligibilityResult]]):
    """Deterministic eligibility engine; LLM only phrases explanations."""

    name = "eligibility_intelligence"

    def __init__(
        self,
        llm: LLMPort | None = None,
        evaluator: RuleEvaluator | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """Inject an optional LLM (for explanations), the rule engine, and a logger."""
        self._llm = llm
        self._evaluator = evaluator or RuleEvaluator()
        self._logger = logger or get_logger(__name__)

    def run(self, data: EligibilityInput, ctx: AgentContext) -> list[EligibilityResult]:
        """Evaluate the profile against every scheme and return one result each."""
        return [self._evaluate(data, scheme, ctx) for scheme in data.schemes]

    def _evaluate(
        self, data: EligibilityInput, scheme: Scheme, ctx: AgentContext
    ) -> EligibilityResult:
        checks = self._evaluator.evaluate(
            data.profile, scheme.eligibility_criteria, data.validated_doc_types
        )
        status, score, confidence = self._aggregate(checks)
        missing_fields = sorted({c.missing_field for c in checks if c.missing_field})
        explanation = self._explain(
            status, scheme, checks, missing_fields, use_llm=data.use_llm_fallback
        )
        return EligibilityResult(
            citizen_id=data.profile.id,
            scheme_id=scheme.id,
            status=status,
            score=round(score, 4),
            confidence=round(confidence, 4),
            evaluations=[c.evaluation for c in checks],
            missing_profile_fields=missing_fields,
            explanation=explanation,
            evaluated_at=ctx.now,
        )

    @staticmethod
    def _aggregate(checks: list[CriterionCheck]) -> tuple[EligibilityStatus, float, float]:
        total = len(checks)
        if total == 0:
            # No structured criteria: treat as open, but flag low confidence.
            return EligibilityStatus.ELIGIBLE, 1.0, 0.5
        passed = sum(1 for c in checks if c.outcome == "pass")
        evaluable = sum(1 for c in checks if c.outcome in ("pass", "fail"))
        score = passed / total
        confidence = evaluable / total
        if any(c.outcome == "fail" for c in checks):
            status = EligibilityStatus.NOT_ELIGIBLE
        elif any(c.outcome == "missing" for c in checks):
            status = EligibilityStatus.NEEDS_MORE_INFO
        else:
            status = EligibilityStatus.ELIGIBLE
        return status, score, confidence

    def _explain(
        self,
        status: EligibilityStatus,
        scheme: Scheme,
        checks: list[CriterionCheck],
        missing_fields: list[str],
        *,
        use_llm: bool,
    ) -> str:
        deterministic = self._deterministic_explanation(status, scheme, checks, missing_fields)
        rules_text = scheme.eligibility_criteria.raw_rules_text
        if not (use_llm and self._llm is not None and rules_text):
            return deterministic
        prompt = (
            f"Decision: {status.value}\nScheme: {scheme.name}\n"
            f"Structured result: {deterministic}\nAdditional unstructured rules: {rules_text}\n"
            "Write the advisory explanation."
        )
        try:
            text = self._llm.complete(prompt, system=EXPLAIN_SYSTEM, temperature=0.0).strip()
        except Exception as exc:  # noqa: BLE001 - explanation is best-effort; never fail the decision
            self._logger.warning("LLM explanation failed; using deterministic text", exc_info=exc)
            return deterministic
        if not text:
            return deterministic
        # Enforce the advisory disclaimer + source in code; the LLM only phrases the body.
        suffix = " This is advisory only; please verify on the official scheme portal."
        if scheme.source_url:
            suffix += f" Source: {scheme.source_url}."
        return f"{text}{suffix}"

    @staticmethod
    def _deterministic_explanation(
        status: EligibilityStatus,
        scheme: Scheme,
        checks: list[CriterionCheck],
        missing_fields: list[str],
    ) -> str:
        parts: list[str] = []
        if status is EligibilityStatus.ELIGIBLE:
            parts.append(
                "Based on the information provided, you appear to meet the criteria for "
                f"{scheme.name}."
            )
        elif status is EligibilityStatus.NOT_ELIGIBLE:
            unmet = ", ".join(c.evaluation.criterion for c in checks if c.outcome == "fail")
            parts.append(
                f"Based on the information provided, you may not currently meet the criteria for "
                f"{scheme.name} (unmet: {unmet})."
            )
        else:
            parts.append(
                f"More information is needed to assess {scheme.name}: {', '.join(missing_fields)}."
            )
        parts.append("This is advisory only; please verify on the official scheme portal.")
        if scheme.source_url:
            parts.append(f"Source: {scheme.source_url}.")
        return " ".join(parts)
