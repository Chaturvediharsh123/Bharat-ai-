"""bharatai.orchestration.state — the shared LangGraph state.

BharatState embeds canonical domain objects verbatim so a node only ever reads/writes
typed domain data. Trace fields (completed_nodes/messages/errors) accumulate via reducers;
all other fields are last-write. 'now' is carried in state so every node shares one clock.
"""
from __future__ import annotations

import operator
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from bharatai.agents.bureaucracy_translator_agent import TranslationResult
from bharatai.agents.recommendation_agent import Recommendation
from bharatai.domain.application import ApplicationHistoryEntry
from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.document import DocumentRecord
from bharatai.domain.eligibility import EligibilityResult
from bharatai.domain.enums import DocumentType
from bharatai.domain.reminder import Reminder
from bharatai.domain.scheme import Scheme


class NodeError(BaseModel):
    """A structured failure recorded by a node so one failure degrades the run."""

    model_config = ConfigDict(extra="forbid")

    node: str
    error_type: str
    message: str


class BharatState(BaseModel):
    """The shared graph state threaded through every agent node."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    now: datetime
    locale: str = "en"
    target_language: str = "en"
    lead_days: int = 7

    # Seeded by the caller before invoking the graph.
    raw_input: dict[str, Any] = Field(default_factory=dict)
    requested_scheme_id: str | None = None
    candidate_schemes: list[Scheme] = Field(default_factory=list)
    applications: list[ApplicationHistoryEntry] = Field(default_factory=list)
    existing_reminders: list[Reminder] = Field(default_factory=list)
    uploaded_documents: list[DocumentRecord] = Field(default_factory=list)

    # Produced by the nodes.
    citizen_profile: CitizenProfile | None = None
    discovered_schemes: list[Scheme] = Field(default_factory=list)
    document_reports: list[DocumentRecord] = Field(default_factory=list)
    validated_doc_types: list[DocumentType] = Field(default_factory=list)
    readiness_score: int | None = None
    eligibility_results: list[EligibilityResult] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    reminders: list[Reminder] = Field(default_factory=list)
    translations: list[TranslationResult] = Field(default_factory=list)

    # Accumulating trace (reducer-merged).
    completed_nodes: Annotated[list[str], operator.add] = Field(default_factory=list)
    messages: Annotated[list[str], operator.add] = Field(default_factory=list)
    errors: Annotated[list[NodeError], operator.add] = Field(default_factory=list)
