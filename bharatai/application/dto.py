"""bharatai.application.dto — cross-layer request/response DTOs.

These are framework-agnostic data shapes returned by ports/services when a core
domain entity is not the right shape (e.g. RAG retrieval and grounded answers).
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from bharatai.domain.identity import Role


class TokenClaims(BaseModel):
    """The verified contents of a session token."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    role: Role
    expires_at: datetime


class RetrievedChunk(BaseModel):
    """A chunk of source text returned by the knowledge base, with provenance + score.

    ``score`` is the cosine similarity to the query (higher = more relevant); it is
    0.0 for a chunk that is merely stored (not yet matched against a query).
    """

    model_config = ConfigDict(extra="forbid")

    text: str
    score: float = 0.0
    source_id: str | None = None  # e.g. the Scheme id
    source_title: str | None = None
    source_url: str | None = None
    chunk_id: str | None = None


class GroundedAnswerStatus(str, Enum):
    """Whether the knowledge base could ground an answer in retrieved sources."""

    ANSWERED = "answered"
    NO_ANSWER = "no_answer"


class GroundedAnswer(BaseModel):
    """An answer that is either grounded in cited sources or an explicit abstention."""

    model_config = ConfigDict(extra="forbid")

    text: str
    status: GroundedAnswerStatus
    citations: list[RetrievedChunk] = Field(default_factory=list)
    confidence: float = 0.0
