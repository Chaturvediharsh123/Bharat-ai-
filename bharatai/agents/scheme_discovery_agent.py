"""bharatai.agents.scheme_discovery_agent — (3) discover relevant schemes via RAG.

Ranks the candidate schemes for a citizen using the knowledge base (FAISS retrieval over
scheme text). Returns the most relevant active schemes. If a specific scheme was requested,
it short-circuits to that one; if retrieval yields nothing, it falls back to all active schemes.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict

from bharatai.agents.base import AgentContext, BaseAgent
from bharatai.application.ports.knowledge import KnowledgeBasePort
from bharatai.common.logging import get_logger
from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.scheme import Scheme


class DiscoveryInput(BaseModel):
    """A profile, the candidate schemes to rank, and optional narrowing."""

    model_config = ConfigDict(extra="forbid")

    profile: CitizenProfile
    candidate_schemes: list[Scheme]
    top_k: int = 20
    requested_scheme_id: str | None = None


class DiscoveryResult(BaseModel):
    """The ranked, relevant schemes."""

    model_config = ConfigDict(extra="forbid")

    schemes: list[Scheme]


class SchemeDiscoveryAgent(BaseAgent[DiscoveryInput, DiscoveryResult]):
    """Ranks candidate schemes for a profile using knowledge-base retrieval."""

    name = "scheme_discovery"

    def __init__(self, knowledge: KnowledgeBasePort, logger: logging.Logger | None = None) -> None:
        """Inject the knowledge base used for relevance ranking and a logger."""
        self._knowledge = knowledge
        self._logger = logger or get_logger(__name__)

    def run(self, data: DiscoveryInput, ctx: AgentContext) -> DiscoveryResult:
        """Return the relevant active schemes for the profile, most relevant first."""
        active = [scheme for scheme in data.candidate_schemes if scheme.is_active]
        by_id = {scheme.id: scheme for scheme in active}

        if data.requested_scheme_id is not None:
            requested = by_id.get(data.requested_scheme_id)
            return DiscoveryResult(schemes=[requested] if requested else [])

        chunks = self._knowledge.retrieve(self._build_query(data.profile), top_k=data.top_k)
        ordered_ids: list[str] = []
        seen: set[str] = set()
        for chunk in chunks:
            if chunk.source_id and chunk.source_id in by_id and chunk.source_id not in seen:
                ordered_ids.append(chunk.source_id)
                seen.add(chunk.source_id)

        if not ordered_ids:
            # No index / no matches: fall back to all active schemes so the flow proceeds.
            return DiscoveryResult(schemes=active[: data.top_k])
        ranked = [by_id[scheme_id] for scheme_id in ordered_ids]
        return DiscoveryResult(schemes=ranked[: data.top_k])

    @staticmethod
    def _build_query(profile: CitizenProfile) -> str:
        parts: list[str] = ["government welfare schemes"]
        if profile.occupation:
            parts.append(profile.occupation)
        if profile.category is not None:
            parts.append(profile.category.value)
        if profile.gender is not None:
            parts.append(profile.gender.value)
        if profile.address is not None and profile.address.state is not None:
            parts.append(profile.address.state.value)
        if profile.is_bpl:
            parts.append("below poverty line")
        return " ".join(parts)
