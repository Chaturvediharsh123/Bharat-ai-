"""Deterministic fakes for the embedding and knowledge-base ports (offline tests)."""
from __future__ import annotations

import hashlib
import math
import re

from bharatai.application.dto import GroundedAnswer, GroundedAnswerStatus, RetrievedChunk
from bharatai.domain.scheme import Scheme

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class FakeEmbedding:
    """A deterministic bag-of-words embedding (normalized) for offline retrieval tests."""

    def __init__(self, dim: int = 256) -> None:
        self._dim = dim

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self._dim
        for token in _TOKEN_RE.findall(text.lower()):
            bucket = int(hashlib.md5(token.encode()).hexdigest(), 16) % self._dim
            vector[bucket] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]


class FakeKnowledgeBase:
    """A KnowledgeBasePort stand-in returning preset chunks/answer (for agent tests)."""

    def __init__(
        self,
        chunks: list[RetrievedChunk] | None = None,
        answer: GroundedAnswer | None = None,
    ) -> None:
        self._chunks = chunks or []
        self._answer = answer
        self.indexed: list[Scheme] = []

    def rebuild(self, schemes: list[Scheme]) -> int:
        self.indexed = list(schemes)
        return len(self.indexed)

    def ingest(self, schemes: list[Scheme]) -> int:
        return self.rebuild(schemes)

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        return self._chunks[: top_k if top_k is not None else len(self._chunks)]

    def answer(self, query: str) -> GroundedAnswer:
        if self._answer is not None:
            return self._answer
        return GroundedAnswer(
            text="This information is not available in the knowledge base.",
            status=GroundedAnswerStatus.NO_ANSWER,
        )
