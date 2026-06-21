"""bharatai.infrastructure.knowledge.llamaindex_kb — the RAG knowledge-base adapter.

Implements KnowledgeBasePort using LlamaIndex node parsing (chunking), a persisted
FAISS index, local bge embeddings, and the no-hallucination grounding guardrail. All
collaborators (LLM, embedding) are injected as ports so the adapter is testable.
"""
from __future__ import annotations

from bharatai.application.dto import GroundedAnswer, RetrievedChunk
from bharatai.application.ports.llm import EmbeddingPort, LLMPort
from bharatai.config.settings import KnowledgeSettings
from bharatai.domain.scheme import Scheme
from bharatai.infrastructure.knowledge.chunking import build_chunks
from bharatai.infrastructure.knowledge.faiss_store import FaissChunkStore
from bharatai.infrastructure.knowledge.grounding import assemble_grounded_answer


class LlamaIndexFaissKnowledgeBase:
    """KnowledgeBasePort backed by LlamaIndex chunking + FAISS + bge embeddings."""

    def __init__(
        self,
        *,
        llm: LLMPort,
        embedding: EmbeddingPort,
        settings: KnowledgeSettings,
    ) -> None:
        """Inject the LLM, embedding model, and knowledge settings."""
        self._llm = llm
        self._embedding = embedding
        self._settings = settings
        self._store = FaissChunkStore(settings.index_dir)

    def rebuild(self, schemes: list[Scheme]) -> int:
        """Rebuild the FAISS index from scratch for the given (active) schemes.

        Rebuilding with no indexable schemes clears the corpus so retrieval returns
        nothing rather than stale results.
        """
        chunks = build_chunks(schemes, self._settings.chunk_size, self._settings.chunk_overlap)
        if not chunks:
            self._store.clear()
            return 0
        vectors = self._embedding.embed_texts([chunk.text for chunk in chunks])
        self._store.build(chunks, vectors)
        return len(chunks)

    def ingest(self, schemes: list[Scheme]) -> int:
        """Add the given (active) schemes to the corpus, preserving what is already indexed."""
        chunks = build_chunks(schemes, self._settings.chunk_size, self._settings.chunk_overlap)
        if not chunks:
            return 0
        vectors = self._embedding.embed_texts([chunk.text for chunk in chunks])
        self._store.append(chunks, vectors)
        return len(chunks)

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        """Return the most relevant chunks for a query (empty if no index)."""
        query_vector = self._embedding.embed_query(query)
        k = top_k if top_k is not None else self._settings.top_k
        return self._store.search(query_vector, k)

    def answer(self, query: str) -> GroundedAnswer:
        """Return a citation-grounded answer, abstaining when retrieval is weak."""
        chunks = self.retrieve(query)
        return assemble_grounded_answer(
            query, chunks, self._llm, min_score=self._settings.min_score
        )
