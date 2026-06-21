"""bharatai.infrastructure.knowledge.faiss_store — a persisted FAISS chunk store.

Stores L2-normalized chunk vectors in a FAISS ``IndexFlatIP`` (so inner product equals
cosine similarity) alongside the chunk records and a small metadata file. faiss is imported
lazily so the module loads in environments where it is not installed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from bharatai.application.dto import RetrievedChunk
from bharatai.common.exceptions import InfrastructureError


class FaissChunkStore:
    """A FAISS inner-product index over chunk vectors, persisted to a directory."""

    def __init__(self, persist_dir: str | Path) -> None:
        """Bind the store to a directory (created on build/persist)."""
        self._dir = Path(persist_dir)
        self._index: Any = None
        self._chunks: list[RetrievedChunk] = []
        self._dim: int | None = None

    @property
    def _index_path(self) -> Path:
        return self._dir / "index.faiss"

    @property
    def _chunks_path(self) -> Path:
        return self._dir / "chunks.json"

    @property
    def _meta_path(self) -> Path:
        return self._dir / "meta.json"

    def exists(self) -> bool:
        """True if a persisted index is available on disk."""
        return self._index_path.exists() and self._chunks_path.exists()

    def size(self) -> int:
        """Number of chunks currently held in memory."""
        return len(self._chunks)

    def _as_matrix(self, vectors: list[list[float]]) -> Any:
        """Validate and convert a list of equal-length vectors to a 2-D float32 matrix."""
        try:
            matrix = np.asarray(vectors, dtype="float32")
        except ValueError as exc:
            raise InfrastructureError("vectors must form a 2-D matrix of equal length") from exc
        if matrix.ndim != 2:
            raise InfrastructureError("vectors must form a 2-D matrix of equal length")
        if int(matrix.shape[1]) <= 0:
            raise InfrastructureError("embedding dimension must be positive")
        return matrix

    def build(self, chunks: list[RetrievedChunk], vectors: list[list[float]]) -> None:
        """Build the index from chunks and their vectors (replacing any prior), then persist."""
        import faiss

        if len(chunks) != len(vectors):
            raise InfrastructureError("chunks and vectors length mismatch")
        if not chunks:
            raise InfrastructureError("cannot build an empty FAISS index")
        matrix = self._as_matrix(vectors)
        dim = int(matrix.shape[1])
        index = faiss.IndexFlatIP(dim)
        index.add(matrix)
        self._index = index
        self._chunks = list(chunks)
        self._dim = dim
        self._persist()

    def append(self, chunks: list[RetrievedChunk], vectors: list[list[float]]) -> None:
        """Add chunks to the existing index (building one if none exists), then persist."""
        if len(chunks) != len(vectors):
            raise InfrastructureError("chunks and vectors length mismatch")
        if not chunks:
            return
        if self._index is None and self.exists():
            self.load()
        if self._index is None:
            self.build(chunks, vectors)
            return
        matrix = self._as_matrix(vectors)
        if int(matrix.shape[1]) != self._dim:
            raise InfrastructureError(
                f"append dim {int(matrix.shape[1])} != index dim {self._dim}"
            )
        self._index.add(matrix)
        self._chunks.extend(chunks)
        self._persist()

    def clear(self) -> None:
        """Remove the persisted index and reset in-memory state."""
        for path in (self._index_path, self._chunks_path, self._meta_path):
            path.unlink(missing_ok=True)
        self._index = None
        self._chunks = []
        self._dim = None

    def _persist(self) -> None:
        import faiss

        self._dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(self._index_path))
        self._chunks_path.write_text(
            json.dumps([chunk.model_dump() for chunk in self._chunks], ensure_ascii=False),
            encoding="utf-8",
        )
        self._meta_path.write_text(
            json.dumps({"dim": self._dim, "count": len(self._chunks)}), encoding="utf-8"
        )

    def load(self) -> None:
        """Load the persisted index and chunk records from disk (meta.json is advisory)."""
        import faiss

        if not self.exists():
            raise InfrastructureError(f"no FAISS index found at {self._dir}")
        self._index = faiss.read_index(str(self._index_path))
        raw = json.loads(self._chunks_path.read_text(encoding="utf-8"))
        self._chunks = [RetrievedChunk.model_validate(item) for item in raw]
        self._dim = int(self._index.d)  # derive dim from the index itself, not meta.json
        if int(self._index.ntotal) != len(self._chunks):
            raise InfrastructureError(
                f"index/chunks count mismatch ({int(self._index.ntotal)} vs "
                f"{len(self._chunks)}); rebuild the index"
            )

    def search(self, query_vector: list[float], top_k: int) -> list[RetrievedChunk]:
        """Return the top-k most similar chunks (cosine score), or [] if empty."""
        if self._index is None:
            if not self.exists():
                return []
            self.load()
        if not self._chunks or top_k <= 0:
            return []
        if self._dim is not None and len(query_vector) != self._dim:
            raise InfrastructureError(
                f"query dim {len(query_vector)} != index dim {self._dim}; "
                "rebuild the index after changing the embedding model"
            )
        query = np.asarray([query_vector], dtype="float32")
        k = min(top_k, len(self._chunks))
        scores, indices = self._index.search(query, k)
        results: list[RetrievedChunk] = []
        for score, index in zip(scores[0], indices[0], strict=True):
            position = int(index)
            if position < 0 or position >= len(self._chunks):
                continue
            results.append(self._chunks[position].model_copy(update={"score": float(score)}))
        return results
