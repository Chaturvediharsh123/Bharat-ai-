"""bharatai.orchestration.registry — the injected agents the graph binds into nodes.

GraphDependencies is built by the composition root with fully-wired agents (their own
services injected) and passed to build_graph. The graph never constructs agents itself.
"""
from __future__ import annotations

from dataclasses import dataclass

from bharatai.agents.bureaucracy_translator_agent import BureaucracyTranslatorAgent
from bharatai.agents.citizen_profile_agent import CitizenProfileAgent
from bharatai.agents.document_intelligence_agent import DocumentIntelligenceAgent
from bharatai.agents.eligibility_agent import EligibilityIntelligenceAgent
from bharatai.agents.recommendation_agent import RecommendationAgent
from bharatai.agents.reminder_agent import ReminderDeadlineAgent
from bharatai.agents.scheme_discovery_agent import SchemeDiscoveryAgent


@dataclass(frozen=True)
class GraphDependencies:
    """The seven fully-constructed agents wired into the graph's nodes."""

    profile: CitizenProfileAgent
    discovery: SchemeDiscoveryAgent
    document: DocumentIntelligenceAgent
    eligibility: EligibilityIntelligenceAgent
    recommendation: RecommendationAgent
    reminder: ReminderDeadlineAgent
    translator: BureaucracyTranslatorAgent
