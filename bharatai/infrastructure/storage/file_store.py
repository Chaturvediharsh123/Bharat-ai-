"""bharatai.infrastructure.storage.file_store — local uploaded-file storage (FileStorePort).

Saves uploaded bytes under a base directory with a sanitized, random filename (never a
user-controlled path) and reads them back by path, enforcing a maximum size.
"""
from __future__ import annotations

import re
from pathlib import Path

from bharatai.common.exceptions import InfrastructureError
from bharatai.common.ids import new_id

_SAFE_SUFFIX = re.compile(r"[^a-z0-9.]")


class FileStore:
    """Stores and retrieves uploaded document bytes on the local filesystem."""

    def __init__(self, base_dir: str | Path, max_bytes: int = 10_000_000) -> None:
        """Bind the store to a base directory and a maximum file size."""
        self._dir = Path(base_dir)
        self._max_bytes = max_bytes

    def save(self, data: bytes, *, suffix: str = "") -> str:
        """Write bytes under a random sanitized filename and return the stored path."""
        if len(data) > self._max_bytes:
            raise InfrastructureError(f"file exceeds {self._max_bytes} bytes")
        clean = _SAFE_SUFFIX.sub("", suffix.lower())
        if clean and not clean.startswith("."):
            clean = f".{clean}"
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"{new_id()}{clean}"
        path.write_bytes(data)
        return str(path)

    def read(self, file_path: str) -> bytes:
        """Read stored bytes by path, confined to the base directory (raises otherwise)."""
        base = self._dir.resolve()
        try:
            resolved = Path(file_path).resolve(strict=True)
        except OSError as exc:
            raise InfrastructureError(f"file not found: {file_path}") from exc
        if not resolved.is_relative_to(base):
            raise InfrastructureError(f"path escapes the store: {file_path}")
        if not resolved.is_file():
            raise InfrastructureError(f"file not found: {file_path}")
        if resolved.stat().st_size > self._max_bytes:
            raise InfrastructureError(f"file exceeds {self._max_bytes} bytes")
        return resolved.read_bytes()
