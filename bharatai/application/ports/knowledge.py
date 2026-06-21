"""bharatai.application.ports.knowledge — the RAG knowledge-base Protocol (port)."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from bharatai.application.dto import GroundedAnswer, RetrievedChunk
from bharatai.domain.scheme import Scheme


@runtime_checkable
class KnowledgeBasePort(Protocol):
    """Retrieval + citation-grounded generation over the government-scheme corpus."""

    def rebuild(self, schemes: list[Scheme]) -> int:
        """Rebuild the index from scratch for the given schemes; return chunk count."""
        ...

    def ingest(self, schemes: list[Scheme]) -> int:
        """Add the given schemes to the corpus; return chunk count indexed."""
        ...

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        """Return the most relevant chunks for a query (empty if no index/matches)."""
        ...

    def answer(self, query: str) -> GroundedAnswer:
        """Return a citation-grounded answer, or an explicit abstention if unsupported."""
        ...
