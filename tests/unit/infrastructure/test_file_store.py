"""Tests for the FileStore (sanitized save, size guard, path-confined read)."""
from __future__ import annotations

from pathlib import Path

import pytest

from bharatai.common.exceptions import InfrastructureError
from bharatai.infrastructure.storage.file_store import FileStore


def test_save_and_read_roundtrip(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "uploads")
    path = store.save(b"hello", suffix="png")
    assert path.endswith(".png")
    assert Path(path).parent == (tmp_path / "uploads")
    assert store.read(path) == b"hello"


def test_save_sanitizes_suffix_and_never_escapes(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "uploads")
    path = store.save(b"x", suffix="../../etc/passwd")
    assert Path(path).resolve().is_relative_to((tmp_path / "uploads").resolve())


def test_read_rejects_path_outside_base(tmp_path: Path) -> None:
    outside = tmp_path / "secret.txt"
    outside.write_bytes(b"top secret")
    store = FileStore(tmp_path / "uploads")
    with pytest.raises(InfrastructureError, match="escapes the store"):
        store.read(str(outside))


def test_read_missing_file(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "uploads")
    with pytest.raises(InfrastructureError, match="not found"):
        store.read(str(tmp_path / "uploads" / "nope.png"))


def test_read_rejects_oversized_file(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "uploads", max_bytes=4)
    path = (tmp_path / "uploads")
    path.mkdir()
    big = path / "big.bin"
    big.write_bytes(b"123456")
    with pytest.raises(InfrastructureError, match="exceeds"):
        store.read(str(big))
