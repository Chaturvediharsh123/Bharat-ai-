"""Slow integration test: real bge embeddings + FAISS prove the RAG pipeline end-to-end.

Marked ``slow`` (excluded from the default gate) because it loads the sentence-transformers
model on first run. Run explicitly with: pytest -m slow
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("faiss")
pytest.importorskip("sentence_transformers")

from bharatai.application.dto import GroundedAnswerStatus  # noqa: E402
from bharatai.config.settings import KnowledgeSettings  # noqa: E402
from bharatai.domain.scheme import Scheme  # noqa: E402
from bharatai.infrastructure.knowledge.llamaindex_kb import (  # noqa: E402
    LlamaIndexFaissKnowledgeBase,
)
from bharatai.infrastructure.llm.embeddings import SentenceTransformerEmbedding  # noqa: E402
from tests.fakes.fake_llm import FakeLLM  # noqa: E402


def _schemes() -> list[Scheme]:
    return [
        Scheme(
            name="PM-KISAN",
            code="PM-KISAN",
            description="Income support providing financial assistance to small and "
            "marginal farmers for agriculture.",
            source_url="https://pmkisan.gov.in",
        ),
        Scheme(
            name="PMAY",
            code="PMAY",
            description="Housing for All scheme providing a subsidy to build a house "
            "for economically weaker urban families.",
            source_url="https://pmaymis.gov.in",
        ),
    ]


@pytest.mark.slow
def test_real_embedding_retrieves_relevant_scheme(tmp_path: Path) -> None:
    settings = KnowledgeSettings(index_dir=str(tmp_path / "idx"), top_k=2, min_score=0.3)
    kb = LlamaIndexFaissKnowledgeBase(
        llm=FakeLLM("Farmers receive financial support under PM-KISAN."),
        embedding=SentenceTransformerEmbedding(),
        settings=settings,
    )
    kb.rebuild(_schemes())

    results = kb.retrieve("financial help for farmers", top_k=2)
    assert results
    assert results[0].source_title == "PM-KISAN"
    assert results[0].score >= settings.min_score

    answer = kb.answer("what support do farmers get?")
    assert answer.status is GroundedAnswerStatus.ANSWERED
    assert answer.citations[0].source_title == "PM-KISAN"
