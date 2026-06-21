"""Tests for the application services (persistence via an injected UnitOfWork factory)."""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from bharatai.application.ports.repositories import UnitOfWork
from bharatai.application.services.application_service import ApplicationService
from bharatai.application.services.citizen_service import CitizenProfileService
from bharatai.application.services.document_service import DocumentService
from bharatai.application.services.eligibility_service import EligibilityService
from bharatai.application.services.reminder_service import ReminderService
from bharatai.application.services.scheme_service import SchemeService
from bharatai.domain.application import ApplicationHistoryEntry
from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.eligibility import EligibilityResult
from bharatai.domain.enums import (
    ApplicationStatus,
    DocumentType,
    DocumentValidationStatus,
    EligibilityStatus,
)
from bharatai.domain.reminder import Reminder
from bharatai.domain.scheme import Scheme
from bharatai.infrastructure.db.connection import SqliteConnectionFactory
from bharatai.infrastructure.db.unit_of_work import SqliteUnitOfWork
from tests.fakes.fake_file_store import FakeFileStore
from tests.fakes.fake_knowledge import FakeKnowledgeBase


@pytest.fixture
def uow_factory(factory: SqliteConnectionFactory) -> Callable[[], UnitOfWork]:
    def make() -> UnitOfWork:
        return SqliteUnitOfWork(factory)

    return make


def test_citizen_service_insert_then_update(uow_factory: Callable[[], UnitOfWork]) -> None:
    service = CitizenProfileService(uow_factory)
    profile = CitizenProfile(full_name="Asha")
    service.save(profile)
    fetched = service.get(profile.id)
    assert fetched is not None
    fetched.occupation = "weaver"
    service.save(fetched)  # update path
    assert service.get(profile.id).occupation == "weaver"  # type: ignore[union-attr]
    assert len(service.list_all()) == 1


def test_scheme_service_upsert_and_seed(uow_factory: Callable[[], UnitOfWork]) -> None:
    knowledge = FakeKnowledgeBase()
    service = SchemeService(uow_factory, knowledge)
    service.upsert(Scheme(name="PM-KISAN", code="PMK"))
    assert [s.name for s in service.list_active()] == ["PM-KISAN"]
    count = service.seed([Scheme(name="PMAY", code="PMAY")])
    assert count == 2
    assert {s.name for s in knowledge.indexed} == {"PM-KISAN", "PMAY"}  # index rebuilt from active


def test_document_service_upload_and_persist(uow_factory: Callable[[], UnitOfWork]) -> None:
    citizen = CitizenProfile()
    CitizenProfileService(uow_factory).save(citizen)
    service = DocumentService(uow_factory, FakeFileStore())
    record = service.save_upload(citizen.id, DocumentType.PAN, b"img", filename="pan.png")
    assert record.file_path
    assert [d.id for d in service.list_for(citizen.id)] == [record.id]
    analyzed = record.model_copy(update={"validation_status": DocumentValidationStatus.VALID})
    service.save_analyzed([analyzed])
    assert service.list_for(citizen.id)[0].validation_status is DocumentValidationStatus.VALID


def test_reminder_service_save_plan(uow_factory: Callable[[], UnitOfWork]) -> None:
    citizen = CitizenProfile()
    CitizenProfileService(uow_factory).save(citizen)
    service = ReminderService(uow_factory)
    reminder = Reminder(citizen_id=citizen.id, title="apply")
    service.save_plan([reminder], [])
    assert [r.id for r in service.list_for(citizen.id)] == [reminder.id]
    updated = reminder.model_copy(update={"title": "apply now"})
    service.save_plan([], [updated])  # updated -> upsert
    assert service.list_for(citizen.id)[0].title == "apply now"


def test_application_service(uow_factory: Callable[[], UnitOfWork]) -> None:
    citizen, scheme = CitizenProfile(), Scheme(name="X")
    CitizenProfileService(uow_factory).save(citizen)
    SchemeService(uow_factory, FakeKnowledgeBase()).upsert(scheme)
    service = ApplicationService(uow_factory)
    entry = ApplicationHistoryEntry(
        citizen_id=citizen.id, scheme_id=scheme.id, status=ApplicationStatus.SUBMITTED
    )
    service.record(entry)
    assert [e.id for e in service.list_for(citizen.id)] == [entry.id]


def test_eligibility_service_append_and_latest(uow_factory: Callable[[], UnitOfWork]) -> None:
    citizen, scheme = CitizenProfile(), Scheme(name="X")
    CitizenProfileService(uow_factory).save(citizen)
    SchemeService(uow_factory, FakeKnowledgeBase()).upsert(scheme)
    service = EligibilityService(uow_factory)
    service.save_results(
        [
            EligibilityResult(
                citizen_id=citizen.id,
                scheme_id=scheme.id,
                status=EligibilityStatus.NEEDS_MORE_INFO,
                evaluated_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        ]
    )
    service.save_results(
        [
            EligibilityResult(
                citizen_id=citizen.id,
                scheme_id=scheme.id,
                status=EligibilityStatus.ELIGIBLE,
                evaluated_at=datetime(2026, 2, 1, tzinfo=UTC),
            )
        ]
    )
    latest = service.latest_for(citizen.id)
    assert len(latest) == 1
    assert latest[0].status is EligibilityStatus.ELIGIBLE  # newest wins
