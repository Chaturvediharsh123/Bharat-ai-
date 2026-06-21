"""End-to-end RAG tests using a real FAISS index with a deterministic fake embedding."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("faiss")

from bharatai.application.dto import GroundedAnswerStatus, RetrievedChunk  # noqa: E402
from bharatai.common.exceptions import InfrastructureError  # noqa: E402
from bharatai.config.settings import KnowledgeSettings  # noqa: E402
from bharatai.domain.scheme import Scheme  # noqa: E402
from bharatai.infrastructure.knowledge.faiss_store import FaissChunkStore  # noqa: E402
from bharatai.infrastructure.knowledge.llamaindex_kb import (  # noqa: E402
    LlamaIndexFaissKnowledgeBase,
)
from tests.fakes.fake_knowledge import FakeEmbedding  # noqa: E402
from tests.fakes.fake_llm import FakeLLM  # noqa: E402


def _schemes() -> list[Scheme]:
    return [
        Scheme(
            name="PM-KISAN",
            code="PM-KISAN",
            description="Income support money for farmers and agriculture cultivators.",
            source_url="https://pmkisan.gov.in",
        ),
        Scheme(
            name="PMAY Housing",
            code="PMAY",
            description="Housing subsidy to build a pucca house for the urban poor.",
            source_url="https://pmaymis.gov.in",
        ),
        Scheme(
            name="Post Matric Scholarship",
            code="PMS",
            description="Scholarship for student education tuition fees for SC and ST learners.",
            source_url="https://scholarships.gov.in",
        ),
    ]


def _kb(tmp_path: Path, **overrides: object) -> LlamaIndexFaissKnowledgeBase:
    settings = KnowledgeSettings(index_dir=str(tmp_path / "idx"), **overrides)  # type: ignore[arg-type]
    return LlamaIndexFaissKnowledgeBase(
        llm=FakeLLM("Grounded answer about farmers."),
        embedding=FakeEmbedding(),
        settings=settings,
    )


def test_rebuild_and_retrieve_ranks_relevant_scheme(tmp_path: Path) -> None:
    kb = _kb(tmp_path, top_k=3, min_score=0.1)
    assert kb.rebuild(_schemes()) >= 3
    results = kb.retrieve("money for farmers and agriculture", top_k=3)
    assert results
    assert results[0].source_title == "PM-KISAN"
    assert results[0].score >= results[-1].score


def test_answer_is_grounded_when_relevant(tmp_path: Path) -> None:
    kb = _kb(tmp_path, top_k=3, min_score=0.1)
    kb.rebuild(_schemes())
    answer = kb.answer("money for farmers and agriculture cultivators")
    assert answer.status is GroundedAnswerStatus.ANSWERED
    assert answer.citations
    assert answer.citations[0].source_title == "PM-KISAN"
    assert answer.citations[0].source_url == "https://pmkisan.gov.in"


def test_answer_abstains_for_unrelated_query(tmp_path: Path) -> None:
    kb = _kb(tmp_path, top_k=3, min_score=0.35)
    kb.rebuild(_schemes())
    answer = kb.answer("zzzz qqqq vvvv totally unrelated nonsense")
    assert answer.status is GroundedAnswerStatus.NO_ANSWER


def test_retrieve_empty_when_no_index(tmp_path: Path) -> None:
    kb = _kb(tmp_path, top_k=3)
    assert kb.retrieve("anything") == []


def test_index_persists_and_reloads(tmp_path: Path) -> None:
    kb = _kb(tmp_path, top_k=3, min_score=0.1)
    kb.rebuild(_schemes())
    store = FaissChunkStore(str(tmp_path / "idx"))
    assert store.exists()
    store.load()
    assert store.size() >= 3


def test_ingest_is_additive(tmp_path: Path) -> None:
    kb = _kb(tmp_path, top_k=10, min_score=0.0)
    first, second, third = _schemes()
    kb.ingest([first])
    kb.ingest([second, third])
    store = FaissChunkStore(str(tmp_path / "idx"))
    store.load()
    titles = {chunk.source_title for chunk in store._chunks}  # noqa: SLF001
    assert titles == {"PM-KISAN", "PMAY Housing", "Post Matric Scholarship"}


def test_rebuild_empty_clears_corpus(tmp_path: Path) -> None:
    kb = _kb(tmp_path, top_k=3, min_score=0.1)
    kb.rebuild(_schemes())
    assert kb.rebuild([]) == 0
    assert kb.retrieve("money for farmers") == []
    assert not FaissChunkStore(str(tmp_path / "idx")).exists()


def test_search_rejects_dim_mismatch(tmp_path: Path) -> None:
    kb = _kb(tmp_path, top_k=3, min_score=0.1)
    kb.rebuild(_schemes())
    store = FaissChunkStore(str(tmp_path / "idx"))
    store.load()
    with pytest.raises(InfrastructureError, match="query dim"):
        store.search([0.1, 0.2, 0.3], top_k=3)


def test_build_rejects_ragged_vectors(tmp_path: Path) -> None:
    store = FaissChunkStore(str(tmp_path / "idx"))
    chunks = [RetrievedChunk(text="a"), RetrievedChunk(text="b")]
    with pytest.raises(InfrastructureError):
        store.build(chunks, [[1.0, 2.0], [3.0]])


def test_load_detects_index_chunks_desync(tmp_path: Path) -> None:
    kb = _kb(tmp_path, top_k=3, min_score=0.1)
    kb.rebuild(_schemes())
    (tmp_path / "idx" / "chunks.json").write_text("[]", encoding="utf-8")
    with pytest.raises(InfrastructureError, match="count mismatch"):
        FaissChunkStore(str(tmp_path / "idx")).load()
