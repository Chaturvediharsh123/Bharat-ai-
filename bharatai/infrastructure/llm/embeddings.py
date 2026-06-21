"""bharatai.infrastructure.llm.embeddings — local sentence-embedding adapter.

Wraps a sentence-transformers model (default BAAI/bge-small-en-v1.5) behind the
EmbeddingPort. Vectors are L2-normalized so dot-product equals cosine similarity.
The model is loaded lazily on first use.
"""
from __future__ import annotations

from typing import Any


class SentenceTransformerEmbedding:
    """EmbeddingPort backed by a local sentence-transformers model."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", device: str = "cpu") -> None:
        """Store the model name/device; the model loads on first embed call."""
        self._model_name = model_name
        self._device = device
        self._model: Any = None

    def _ensure_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name, device=self._device)
        return self._model

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string into a normalized vector."""
        model = self._ensure_model()
        vector = model.encode([text], normalize_embeddings=True)[0]
        return [float(value) for value in vector]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into normalized vectors."""
        if not texts:
            return []
        model = self._ensure_model()
        vectors = model.encode(list(texts), normalize_embeddings=True)
        return [[float(value) for value in vector] for vector in vectors]
