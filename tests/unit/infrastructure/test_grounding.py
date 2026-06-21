"""Tests for the no-hallucination grounding guardrail (pure, fake LLM)."""
from __future__ import annotations

from bharatai.application.dto import GroundedAnswerStatus, RetrievedChunk
from bharatai.infrastructure.knowledge.grounding import NO_ANSWER_TEXT, assemble_grounded_answer
from tests.fakes.fake_llm import FakeLLM


def _chunk(text: str, score: float, **kwargs: str) -> RetrievedChunk:
    return RetrievedChunk(text=text, score=score, **kwargs)


def test_abstains_when_all_below_threshold() -> None:
    llm = FakeLLM("should never be used")
    chunks = [_chunk("weak a", 0.10), _chunk("weak b", 0.20)]
    answer = assemble_grounded_answer("q", chunks, llm, min_score=0.35)
    assert answer.status is GroundedAnswerStatus.NO_ANSWER
    assert answer.text == NO_ANSWER_TEXT
    assert answer.citations == []
    assert llm.calls == []  # the LLM is never invoked when abstaining


def test_answers_with_only_relevant_citations() -> None:
    llm = FakeLLM("PM-KISAN gives Rs 6000 per year.")
    chunks = [
        _chunk("PM-KISAN income support", 0.80, source_title="PM-KISAN"),
        _chunk("irrelevant", 0.10),
    ]
    answer = assemble_grounded_answer("benefit?", chunks, llm, min_score=0.35)
    assert answer.status is GroundedAnswerStatus.ANSWERED
    assert answer.text == "PM-KISAN gives Rs 6000 per year."
    assert [c.source_title for c in answer.citations] == ["PM-KISAN"]
    assert answer.confidence == 0.80
    assert len(llm.calls) == 1
    assert "context" in (llm.calls[0]["prompt"] or "").lower()


def test_empty_llm_output_falls_back_to_abstention() -> None:
    llm = FakeLLM("   ")
    answer = assemble_grounded_answer("q", [_chunk("relevant", 0.9)], llm, min_score=0.35)
    assert answer.status is GroundedAnswerStatus.NO_ANSWER
