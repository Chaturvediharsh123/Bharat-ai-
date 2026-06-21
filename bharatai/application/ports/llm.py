"""bharatai.application.ports.llm — LLM and embedding Protocols (ports).

Agents and services depend on these abstractions, never on ollama / sentence-transformers
directly, so inference backends are swappable and tests run offline with fakes.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMPort(Protocol):
    """A text-completion model."""

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str: ...


@runtime_checkable
class EmbeddingPort(Protocol):
    """A text-embedding model producing L2-normalized vectors (for cosine via dot-product)."""

    def embed_query(self, text: str) -> list[float]: ...
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...
