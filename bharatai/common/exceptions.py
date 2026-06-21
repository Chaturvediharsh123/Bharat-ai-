"""bharatai.common.exceptions — application-wide exception hierarchy.

A single ``BaseAppError`` root with three sub-trees (domain / application /
infrastructure) so callers can catch at the granularity they need and every
raised error is attributable to a layer.
"""
from __future__ import annotations


class BaseAppError(Exception):
    """Root of every BharatAI error. Never raise this directly — use a subclass."""

    def __init__(self, message: str, *, context: dict[str, object] | None = None) -> None:
        """Store a human-readable message and optional structured context."""
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        """Render the message with any attached context for logs."""
        if self.context:
            return f"{self.message} | context={self.context}"
        return self.message


# ── Domain layer ─────────────────────────────────────────────────────────────
class DomainError(BaseAppError):
    """A rule of the core domain was violated."""


class DomainValidationError(DomainError):
    """An entity or value object failed a domain invariant."""


# ── Application layer ────────────────────────────────────────────────────────
class ApplicationError(BaseAppError):
    """A use-case / service-level failure."""


class EntityNotFoundError(ApplicationError):
    """A requested aggregate does not exist."""


class ConflictError(ApplicationError):
    """An operation conflicts with existing state (e.g. a duplicate email)."""


class AuthenticationError(ApplicationError):
    """Credentials/OTP were missing or invalid."""


class AuthorizationError(ApplicationError):
    """The principal is authenticated but lacks the required permission."""


# ── Infrastructure layer ─────────────────────────────────────────────────────
class InfrastructureError(BaseAppError):
    """An adapter (DB / LLM / OCR / knowledge base) failed."""


class RepositoryError(InfrastructureError):
    """A persistence operation failed."""


class DuplicateEntityError(RepositoryError):
    """Insert violated a uniqueness constraint."""


class MigrationError(InfrastructureError):
    """Applying a database migration failed."""


class SerializationError(InfrastructureError):
    """Converting a domain object to/from its stored representation failed."""
