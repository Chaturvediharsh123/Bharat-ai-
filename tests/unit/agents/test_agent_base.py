"""Tests for the agent base contract."""
from __future__ import annotations

from datetime import datetime

from bharatai.agents.base import Agent, AgentContext
from bharatai.agents.citizen_profile_agent import CitizenProfileAgent


def test_agent_context_defaults() -> None:
    ctx = AgentContext(trace_id="trace-1")
    assert ctx.locale == "en"
    assert ctx.citizen_id is None
    assert isinstance(ctx.now, datetime)


def test_citizen_agent_satisfies_protocol() -> None:
    agent = CitizenProfileAgent()
    assert isinstance(agent, Agent)
    assert agent.name == "citizen_profile"
