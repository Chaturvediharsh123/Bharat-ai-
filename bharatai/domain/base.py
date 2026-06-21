"""bharatai.domain.base — shared pydantic bases for the domain layer.

The domain layer depends on NOTHING outside the standard library and pydantic.
Entities self-generate their id and UTC timestamps so a domain object is valid
before it ever reaches the database.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _new_id() -> str:
    return str(uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DomainModel(BaseModel):
    """Base for mutable domain entities. Forbids unknown fields, validates on assign."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        use_enum_values=False,
    )


class ValueObject(BaseModel):
    """Base for immutable, equality-by-value objects (Money, Address, ...)."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        use_enum_values=False,
    )


class Entity(DomainModel):
    """A persistable aggregate root with a stable id and audit timestamps."""

    id: str = Field(default_factory=_new_id)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    def touch(self) -> None:
        """Advance ``updated_at`` to now (call before persisting an update)."""
        self.updated_at = _utcnow()
