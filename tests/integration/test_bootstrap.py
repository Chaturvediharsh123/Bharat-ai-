"""Integration test: the composition root wires a working container end-to-end."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from bharatai.application.dto import RetrievedChunk
from bharatai.bootstrap.testing import build_test_container
from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.scheme import EligibilityCriteria, Scheme
from bharatai.domain.value_objects import Money
from bharatai.infrastructure.db.connection import SqliteConnectionFactory
from bharatai.infrastructure.ocr.service import DocumentIntelligenceService
from bharatai.orchestration.state import BharatState
from tests.fakes.fake_file_store import FakeFileStore
from tests.fakes.fake_knowledge import FakeKnowledgeBase
from tests.fakes.fake_llm import FakeLLM
from tests.fakes.fake_ocr import FakeOcr

_NOW = datetime(2026, 6, 20, tzinfo=UTC)


def _container(tmp_path: Path, scheme: Scheme):  # type: ignore[no-untyped-def]
    factory = SqliteConnectionFactory(tmp_path / "bootstrap.db")
    knowledge = FakeKnowledgeBase(
        chunks=[RetrievedChunk(text="income support", source_id=scheme.id)]
    )
    return build_test_container(
        factory,
        knowledge=knowledge,
        llm=FakeLLM("explanation"),
        file_store=FakeFileStore(),
        document_analyzer=DocumentIntelligenceService(FakeOcr("Name: Asha Devi")),
    )


def test_services_round_trip_and_graph_runs(tmp_path: Path) -> None:
    scheme = Scheme(
        name="PM-KISAN",
        eligibility_criteria=EligibilityCriteria(max_annual_income=Money(amount=Decimal("200000"))),
    )
    services = _container(tmp_path, scheme).services

    # Scheme + citizen persistence via services.
    services.schemes.upsert(scheme)
    assert [s.name for s in services.schemes.list_active()] == ["PM-KISAN"]
    profile = CitizenProfile(full_name="Asha Devi")
    services.citizens.save(profile)
    loaded = services.citizens.get(profile.id)
    assert loaded is not None and loaded.full_name == "Asha Devi"

    # Run the whole graph through the wired runner.
    state = BharatState(
        run_id="run-1",
        now=_NOW,
        raw_input={"name": "Asha Devi", "income": "150000"},
        candidate_schemes=services.schemes.list_active(),
    )
    out = services.graph_runner.run(state)
    assert out.errors == []
    assert out.citizen_profile is not None
    assert out.eligibility_results
    assert out.discovered_schemes


def test_eligibility_and_reminder_services_persist(tmp_path: Path) -> None:
    scheme = Scheme(name="PMAY")
    services = _container(tmp_path, scheme).services
    services.schemes.upsert(scheme)
    profile = CitizenProfile(full_name="Ravi")
    services.citizens.save(profile)

    state = BharatState(
        run_id="run-2",
        now=_NOW,
        raw_input={"name": "Ravi"},
        candidate_schemes=services.schemes.list_active(),
    )
    out = services.graph_runner.run(state)
    # Persist results produced by the run, keyed to the saved citizen.
    results = [r.model_copy(update={"citizen_id": profile.id}) for r in out.eligibility_results]
    services.eligibility.save_results(results)
    assert len(services.eligibility.latest_for(profile.id)) == len(results)
