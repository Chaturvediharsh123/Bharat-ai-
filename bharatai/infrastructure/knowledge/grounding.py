"""bharatai.infrastructure.knowledge.grounding — the no-hallucination guardrail.

Pure answer-assembly logic, independent of FAISS/embeddings so it is unit-testable
with a fake LLM. Three layers prevent hallucination:
  1. a hard min-score threshold drops weak retrievals before the LLM sees them;
  2. an abstain path returns a fixed NO_ANSWER when nothing relevant remains;
  3. the system prompt forbids using anything outside the provided context, and every
     answer carries its source citations.
"""
from __future__ import annotations

from bharatai.application.dto import GroundedAnswer, GroundedAnswerStatus, RetrievedChunk
from bharatai.application.ports.llm import LLMPort

NO_ANSWER_TEXT = "This information is not available in the knowledge base."

GROUNDING_SYSTEM_PROMPT = (
    "You are BharatAI, a careful assistant for Indian government schemes. "
    "Answer ONLY using the provided context. If the context does not contain the answer, "
    "reply exactly: 'This information is not available in the knowledge base.' "
    "Never invent scheme names, amounts, dates, or eligibility rules. "
    "Keep numbers, thresholds, and dates exactly as written in the context."
)


def _format_context(chunks: list[RetrievedChunk]) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        source = chunk.source_title or chunk.source_id or "source"
        blocks.append(f"[{index}] ({source})\n{chunk.text}")
    return "\n\n".join(blocks)


def build_prompt(query: str, chunks: list[RetrievedChunk]) -> str:
    """Build the grounded-generation prompt from the query and retrieved context."""
    return f"Context:\n{_format_context(chunks)}\n\nQuestion: {query}\n\nAnswer:"


def assemble_grounded_answer(
    query: str,
    chunks: list[RetrievedChunk],
    llm: LLMPort,
    *,
    min_score: float,
    no_answer_text: str = NO_ANSWER_TEXT,
) -> GroundedAnswer:
    """Apply the no-hallucination guardrail and return a grounded answer or abstention."""
    relevant = [chunk for chunk in chunks if chunk.score >= min_score]
    if not relevant:
        return GroundedAnswer(text=no_answer_text, status=GroundedAnswerStatus.NO_ANSWER)

    prompt = build_prompt(query, relevant)
    text = llm.complete(prompt, system=GROUNDING_SYSTEM_PROMPT, temperature=0.0).strip()
    if not text:
        return GroundedAnswer(text=no_answer_text, status=GroundedAnswerStatus.NO_ANSWER)

    return GroundedAnswer(
        text=text,
        status=GroundedAnswerStatus.ANSWERED,
        citations=relevant,
        confidence=relevant[0].score,
    )
