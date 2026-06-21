"""Fake FileStorePort for offline tests."""
from __future__ import annotations


class FakeFileStore:
    """Returns preset bytes per path, a default for unknown paths, or raises if none."""

    def __init__(
        self, files: dict[str, bytes] | None = None, default: bytes | None = b"image-bytes"
    ) -> None:
        self._files = files or {}
        self._default = default

    def save(self, data: bytes, *, suffix: str = "") -> str:
        path = f"/fake/{len(self._files)}{suffix}"
        self._files[path] = data
        return path

    def read(self, file_path: str) -> bytes:
        if file_path in self._files:
            return self._files[file_path]
        if self._default is not None:
            return self._default
        raise FileNotFoundError(file_path)
