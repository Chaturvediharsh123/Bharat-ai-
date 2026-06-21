"""Tests for the SchemeDiscoveryAgent (RAG ranking of candidate schemes)."""
from __future__ import annotations

from bharatai.agents.base import AgentContext
from bharatai.agents.scheme_discovery_agent import DiscoveryInput, SchemeDiscoveryAgent
from bharatai.application.dto import RetrievedChunk
from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.scheme import Scheme
from tests.fakes.fake_knowledge import FakeKnowledgeBase

_CTX = AgentContext(trace_id="trace-1")


def test_ranks_by_retrieval_order() -> None:
    a, b, c = Scheme(name="A"), Scheme(name="B"), Scheme(name="C")
    kb = FakeKnowledgeBase(
        chunks=[RetrievedChunk(text="x", source_id=b.id), RetrievedChunk(text="y", source_id=c.id)]
    )
    agent = SchemeDiscoveryAgent(kb)
    result = agent.run(
        DiscoveryInput(profile=CitizenProfile(), candidate_schemes=[a, b, c]), _CTX
    )
    assert [s.name for s in result.schemes] == ["B", "C"]  # A was not retrieved


def test_requested_scheme_short_circuits() -> None:
    a, b = Scheme(name="A"), Scheme(name="B")
    agent = SchemeDiscoveryAgent(FakeKnowledgeBase())
    result = agent.run(
        DiscoveryInput(
            profile=CitizenProfile(), candidate_schemes=[a, b], requested_scheme_id=b.id
        ),
        _CTX,
    )
    assert [s.name for s in result.schemes] == ["B"]


def test_falls_back_to_active_schemes_without_retrieval() -> None:
    a, inactive = Scheme(name="A"), Scheme(name="Old", is_active=False)
    agent = SchemeDiscoveryAgent(FakeKnowledgeBase(chunks=[]))
    result = agent.run(
        DiscoveryInput(profile=CitizenProfile(), candidate_schemes=[a, inactive]), _CTX
    )
    assert [s.name for s in result.schemes] == ["A"]  # inactive excluded; fallback to active
