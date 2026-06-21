"""bharatai.agents.bureaucracy_translator_agent — (5) plain-language simplification.

Simplifies dense bureaucratic text into plain language (and optionally translates it to an
Indian language) via the injected LLM. To guard citizen trust, it preserves the original
text, post-checks that numbers/amounts/dates survived the rewrite, and flags machine
translation. LLM failures degrade to showing the original — they never crash the run.
"""
from __future__ import annotations

import logging
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from bharatai.agents.base import AgentContext, BaseAgent
from bharatai.application.ports.llm import LLMPort
from bharatai.common.logging import get_logger

SIMPLIFY_SYSTEM = (
    "You simplify Indian government and bureaucratic text into clear, plain language for "
    "ordinary citizens. Preserve every number, amount, date, percentage, and eligibility "
    "condition EXACTLY as written. Do not add facts, omit conditions, or change any figure."
)
_ENGLISH = {"en", "english"}
_NUMBER_RE = re.compile(r"\d{2,}")


def _digit_runs(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(text.replace(",", "")))


def _missing_numbers(source: str, output: str) -> set[str]:
    output_digits = re.sub(r"\D", "", output)
    return {number for number in _digit_runs(source) if number not in output_digits}


class TranslateInput(BaseModel):
    """Text to simplify, the target language, reading level, and an optional glossary."""

    model_config = ConfigDict(extra="forbid")

    text: str
    target_language: str = "en"
    reading_level: Literal["simple", "standard"] = "simple"
    glossary: dict[str, str] = Field(default_factory=dict)


class TranslationResult(BaseModel):
    """The simplified text alongside the original, with provenance flags and warnings."""

    model_config = ConfigDict(extra="forbid")

    original_text: str
    simplified_text: str
    target_language: str
    is_machine_translation: bool
    warnings: list[str] = Field(default_factory=list)


class BureaucracyTranslatorAgent(BaseAgent[TranslateInput, TranslationResult]):
    """Simplifies/translates bureaucratic text while preserving facts and the original."""

    name = "bureaucracy_translator"

    def __init__(self, llm: LLMPort, logger: logging.Logger | None = None) -> None:
        """Inject the LLM used to phrase the simplification and a logger."""
        self._llm = llm
        self._logger = logger or get_logger(__name__)

    def run(self, data: TranslateInput, ctx: AgentContext) -> TranslationResult:
        """Simplify (and optionally translate) the text, preserving the original and facts."""
        is_machine_translation = data.target_language.lower() not in _ENGLISH
        text = data.text.strip()
        if not text:
            return TranslationResult(
                original_text=data.text,
                simplified_text="",
                target_language=data.target_language,
                is_machine_translation=False,
                warnings=["input text was empty"],
            )

        try:
            output = self._llm.complete(
                self._build_prompt(data), system=SIMPLIFY_SYSTEM, temperature=0.0
            ).strip()
        except Exception as exc:  # noqa: BLE001 - simplification is best-effort; never crash
            self._logger.warning("translation LLM failed; showing original", exc_info=exc)
            return TranslationResult(
                original_text=data.text,
                simplified_text=text,
                target_language=data.target_language,
                is_machine_translation=False,
                warnings=["simplification is unavailable; showing the original text"],
            )

        warnings: list[str] = []
        if not output:
            output = text
            warnings.append("simplification is unavailable; showing the original text")

        missing = _missing_numbers(text, output)
        if missing:
            warnings.append(
                "some numbers or dates may differ from the original — please verify: "
                + ", ".join(sorted(missing))
            )
        if is_machine_translation:
            warnings.append(
                "machine-translated; refer to the official English text for accuracy"
            )

        return TranslationResult(
            original_text=data.text,
            simplified_text=output,
            target_language=data.target_language,
            is_machine_translation=is_machine_translation,
            warnings=warnings,
        )

    @staticmethod
    def _build_prompt(data: TranslateInput) -> str:
        lines = [
            f"Simplify the following government text into clear, plain language "
            f"({data.reading_level} reading level)."
        ]
        if data.target_language.lower() not in _ENGLISH:
            lines.append(f"Then translate it into {data.target_language}.")
        lines.append("Preserve every number, amount, date, percentage, and condition exactly.")
        if data.glossary:
            terms = "; ".join(f"{term} = {plain}" for term, plain in data.glossary.items())
            lines.append(f"Use these plain-language terms where relevant: {terms}.")
        lines.append(f"\nText:\n{data.text}")
        return "\n".join(lines)
