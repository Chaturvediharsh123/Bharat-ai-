"""End-to-end test of the compiled LangGraph wiring all 7 agents (offline, with fakes)."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

from bharatai.agents.bureaucracy_translator_agent import BureaucracyTranslatorAgent
from bharatai.agents.citizen_profile_agent import CitizenProfileAgent
from bharatai.agents.document_intelligence_agent import DocumentIntelligenceAgent
from bharatai.agents.eligibility_agent import EligibilityIntelligenceAgent
from bharatai.agents.recommendation_agent import RecommendationAgent
from bharatai.agents.reminder_agent import ReminderDeadlineAgent
from bharatai.agents.scheme_discovery_agent import SchemeDiscoveryAgent
from bharatai.application.dto import RetrievedChunk
from bharatai.domain.enums import EligibilityStatus
from bharatai.domain.scheme import EligibilityCriteria, Scheme
from bharatai.domain.value_objects import DateRange, Money
from bharatai.infrastructure.ocr.service import DocumentIntelligenceService
from bharatai.orchestration.registry import GraphDependencies
from bharatai.orchestration.runner import BharatGraphRunner
from bharatai.orchestration.state import BharatState
from tests.fakes.fake_file_store import FakeFileStore
from tests.fakes.fake_knowledge import FakeKnowledgeBase
from tests.fakes.fake_llm import FakeLLM
from tests.fakes.fake_ocr import FakeOcr

_NOW = datetime(2026, 6, 20, tzinfo=UTC)


class _RaisingProfileAgent:
    name = "citizen_profile"

    def run(self, data: object, ctx: object) -> object:
        raise RuntimeError("profile build failed")


class _RaisingKnowledgeBase:
    def rebuild(self, schemes: object) -> int:
        return 0

    def ingest(self, schemes: object) -> int:
        return 0

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        raise RuntimeError("knowledge base unavailable")

    def answer(self, query: str) -> object:
        raise RuntimeError("knowledge base unavailable")


def _deps(knowledge: object) -> GraphDependencies:
    return GraphDependencies(
        profile=CitizenProfileAgent(),
        discovery=SchemeDiscoveryAgent(knowledge),  # type: ignore[arg-type]
        document=DocumentIntelligenceAgent(
            analyzer=DocumentIntelligenceService(FakeOcr("Name: Asha Devi")),
            file_store=FakeFileStore(),
        ),
        eligibility=EligibilityIntelligenceAgent(llm=FakeLLM("explanation")),
        recommendation=RecommendationAgent(),
        reminder=ReminderDeadlineAgent(),
        translator=BureaucracyTranslatorAgent(FakeLLM("anuvaad 150000")),
    )


def _scheme() -> Scheme:
    return Scheme(
        name="PM-KISAN",
        eligibility_criteria=EligibilityCriteria(max_annual_income=Money(amount=Decimal("200000"))),
        application_window=DateRange(end=date(2026, 12, 31)),
        source_url="https://pmkisan.gov.in",
    )


def _initial_state(scheme: Scheme, **kwargs: object) -> BharatState:
    return BharatState(
        run_id="run-1",
        now=_NOW,
        raw_input={"name": "Asha Devi", "income": "150000"},
        candidate_schemes=[scheme],
        **kwargs,  # type: ignore[arg-type]
    )


def test_full_pipeline_runs_all_relevant_nodes() -> None:
    scheme = _scheme()
    knowledge = FakeKnowledgeBase(
        chunks=[RetrievedChunk(text="income support for farmers", source_id=scheme.id)]
    )
    runner = BharatGraphRunner.from_dependencies(_deps(knowledge))
    out = runner.run(_initial_state(scheme))

    assert out.errors == []
    assert out.citizen_profile is not None
    assert out.citizen_profile.full_name == "Asha Devi"
    assert [s.name for s in out.discovered_schemes] == ["PM-KISAN"]
    assert len(out.eligibility_results) == 1
    assert out.eligibility_results[0].status is EligibilityStatus.ELIGIBLE
    assert out.recommendations  # eligible but not applied
    assert out.reminders  # scheme has a deadline
    assert {
        "profile",
        "discovery",
        "eligibility",
        "recommendation",
        "reminder",
        "aggregate",
    }.issubset(set(out.completed_nodes))
    # English target -> translator and (no uploads) document nodes are skipped.
    assert "translator" not in out.completed_nodes
    assert "document" not in out.completed_nodes


def test_translator_node_runs_for_non_english_target() -> None:
    scheme = _scheme()
    knowledge = FakeKnowledgeBase(
        chunks=[RetrievedChunk(text="income support", source_id=scheme.id)]
    )
    runner = BharatGraphRunner.from_dependencies(_deps(knowledge))
    out = runner.run(_initial_state(scheme, target_language="hi"))
    assert "translator" in out.completed_nodes
    assert out.translations
    assert out.translations[0].is_machine_translation is True


def test_single_node_failure_is_isolated() -> None:
    scheme = _scheme()
    runner = BharatGraphRunner.from_dependencies(_deps(_RaisingKnowledgeBase()))
    out = runner.run(_initial_state(scheme))
    # Discovery failed, but the run completed and recorded the error.
    assert any(e.node == "discovery" for e in out.errors)
    assert "discovery" not in out.completed_nodes
    assert "aggregate" in out.completed_nodes  # pipeline still finished
    assert out.discovered_schemes == []


def test_skipped_nodes_are_not_marked_completed() -> None:
    scheme = _scheme()
    deps = replace(_deps(FakeKnowledgeBase()), profile=_RaisingProfileAgent())  # type: ignore[arg-type]
    runner = BharatGraphRunner.from_dependencies(deps)
    out = runner.run(_initial_state(scheme))
    assert any(e.node == "profile" for e in out.errors)
    # downstream nodes skipped (no profile) -> must NOT appear as completed
    assert "discovery" not in out.completed_nodes
    assert "eligibility" not in out.completed_nodes
    assert "aggregate" in out.completed_nodes  # the run still finishes
