"""Tests for the BureaucracyTranslatorAgent (simplify + fact-preservation + MT flag)."""
from __future__ import annotations

from bharatai.agents.base import AgentContext
from bharatai.agents.bureaucracy_translator_agent import (
    BureaucracyTranslatorAgent,
    TranslateInput,
)
from tests.fakes.fake_llm import FakeLLM

_CTX = AgentContext(trace_id="trace-1")


class _RaisingLLM:
    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        raise RuntimeError("llm unavailable")


def test_simplifies_and_preserves_numbers() -> None:
    text = "The applicant must have annual income below Rs 2,50,000 to qualify."
    llm = FakeLLM("You can apply if you earn less than Rs 250000 per year.")
    result = BureaucracyTranslatorAgent(llm).run(TranslateInput(text=text), _CTX)
    assert result.simplified_text.startswith("You can apply")
    assert result.original_text == text
    assert result.is_machine_translation is False
    assert result.warnings == []


def test_warns_when_a_number_is_dropped() -> None:
    text = "Income must be below Rs 2,50,000."
    llm = FakeLLM("Income must be low.")  # drops the figure
    result = BureaucracyTranslatorAgent(llm).run(TranslateInput(text=text), _CTX)
    assert any("verify" in w for w in result.warnings)
    assert any("250000" in w for w in result.warnings)


def test_machine_translation_is_flagged() -> None:
    llm = FakeLLM("कम आय वाले नागरिकों के लिए।")
    result = BureaucracyTranslatorAgent(llm).run(
        TranslateInput(text="For low-income citizens.", target_language="hi"), _CTX
    )
    assert result.is_machine_translation is True
    assert any("machine-translated" in w for w in result.warnings)


def test_llm_failure_returns_original() -> None:
    result = BureaucracyTranslatorAgent(_RaisingLLM()).run(
        TranslateInput(text="Some dense bureaucratic text."), _CTX
    )
    assert result.simplified_text == "Some dense bureaucratic text."
    assert any("unavailable" in w for w in result.warnings)


def test_empty_input() -> None:
    result = BureaucracyTranslatorAgent(FakeLLM("x")).run(TranslateInput(text="   "), _CTX)
    assert result.simplified_text == ""
    assert any("empty" in w for w in result.warnings)
