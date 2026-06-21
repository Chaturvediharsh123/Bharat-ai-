"""Shared pytest fixtures for BharatAI: a freshly-migrated SQLite database + UoW."""
from __future__ import annotations

from pathlib import Path

import pytest

from bharatai.infrastructure.db.connection import SqliteConnectionFactory
from bharatai.infrastructure.db.unit_of_work import SqliteUnitOfWork


@pytest.fixture
def factory(tmp_path: Path) -> SqliteConnectionFactory:
    """A connection factory backed by a temp DB file, schema already applied."""
    f = SqliteConnectionFactory(tmp_path / "bharatai_test.db")
    f.initialize()
    return f


@pytest.fixture
def uow(factory: SqliteConnectionFactory) -> SqliteUnitOfWork:
    """A UnitOfWork over the temp database (open a `with` block per transaction)."""
    return SqliteUnitOfWork(factory)
