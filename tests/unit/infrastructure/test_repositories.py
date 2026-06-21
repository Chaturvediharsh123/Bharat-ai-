"""Tests for scheme/eligibility/reminder repositories, cascade deletes, migrations."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from bharatai.common.exceptions import (
    DuplicateEntityError,
    MigrationError,
    RepositoryError,
    SerializationError,
)
from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.eligibility import CriterionEvaluation, EligibilityResult
from bharatai.domain.enums import DocumentType, EligibilityStatus, ReminderStatus
from bharatai.domain.reminder import Reminder
from bharatai.domain.scheme import EligibilityCriteria, Scheme, SchemeBenefit
from bharatai.domain.value_objects import DateRange, Money
from bharatai.infrastructure.db import mappers
from bharatai.infrastructure.db.connection import SqliteConnectionFactory, apply_migrations
from bharatai.infrastructure.db.unit_of_work import SqliteUnitOfWork

_TABLES = {
    "citizen_profiles",
    "schemes",
    "eligibility_results",
    "documents",
    "reminders",
    "application_history",
}


def _scheme(code: str = "PM-KISAN") -> Scheme:
    return Scheme(
        name="PM-KISAN",
        code=code,
        description="Income support for farmers",
        eligibility_criteria=EligibilityCriteria(
            max_annual_income=Money(amount=Decimal("200000.00")),
            required_documents=[DocumentType.AADHAAR],
        ),
        benefits=[
            SchemeBenefit(
                description="Rs 6000 per year",
                amount=Money(amount=Decimal("6000.00")),
                frequency="annual",
            )
        ],
        application_window=DateRange(start=date(2025, 1, 1), end=date(2025, 12, 31)),
        source_url="https://pmkisan.gov.in",
        verified_at=date(2026, 6, 1),
    )


def test_scheme_roundtrip_and_active(uow: SqliteUnitOfWork) -> None:
    scheme = _scheme()
    with uow:
        uow.schemes.add(scheme)
    with uow as u:
        assert u.schemes.get(scheme.id) == scheme
        assert [s.id for s in u.schemes.list_active()] == [scheme.id]


def test_scheme_upsert_by_code_updates_in_place(uow: SqliteUnitOfWork) -> None:
    scheme = _scheme()
    with uow:
        uow.schemes.add(scheme)
    with uow as u:
        replacement = _scheme()
        replacement.description = "Updated description"
        u.schemes.upsert_by_code(replacement)
    with uow as u:
        active = u.schemes.list_active()
    assert len(active) == 1
    assert active[0].id == scheme.id
    assert active[0].description == "Updated description"


def test_eligibility_is_append_only_with_latest(uow: SqliteUnitOfWork) -> None:
    citizen = CitizenProfile(full_name="Test User")
    scheme = _scheme()
    with uow:
        uow.citizens.add(citizen)
        uow.schemes.add(scheme)
        uow.eligibility_results.add(
            EligibilityResult(
                citizen_id=citizen.id,
                scheme_id=scheme.id,
                status=EligibilityStatus.NEEDS_MORE_INFO,
                score=0.5,
                confidence=0.5,
                evaluated_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        uow.eligibility_results.add(
            EligibilityResult(
                citizen_id=citizen.id,
                scheme_id=scheme.id,
                status=EligibilityStatus.ELIGIBLE,
                score=1.0,
                confidence=0.9,
                evaluations=[CriterionEvaluation(criterion="income", passed=True)],
                evaluated_at=datetime(2026, 2, 1, tzinfo=UTC),
            )
        )
    with uow as u:
        latest = u.eligibility_results.latest_for(citizen.id, scheme.id)
        assert latest is not None
        assert latest.status == EligibilityStatus.ELIGIBLE
        assert len(u.eligibility_results.list_by_citizen(citizen.id)) == 2


def test_cascade_delete_removes_children(uow: SqliteUnitOfWork) -> None:
    citizen = CitizenProfile(full_name="Cascade User")
    scheme = _scheme(code="SCH-CASCADE")
    with uow:
        uow.citizens.add(citizen)
        uow.schemes.add(scheme)
        uow.eligibility_results.add(
            EligibilityResult(
                citizen_id=citizen.id,
                scheme_id=scheme.id,
                status=EligibilityStatus.ELIGIBLE,
            )
        )
    with uow as u:
        assert u.citizens.delete(citizen.id) is True
    with uow as u:
        assert u.eligibility_results.list_by_citizen(citizen.id) == []


def test_reminder_list_due(uow: SqliteUnitOfWork) -> None:
    citizen = CitizenProfile(full_name="Reminder User")
    with uow:
        uow.citizens.add(citizen)
        uow.reminders.add(
            Reminder(
                citizen_id=citizen.id,
                title="Apply soon",
                due_date=date(2026, 6, 30),
                status=ReminderStatus.SCHEDULED,
            )
        )
        uow.reminders.add(
            Reminder(
                citizen_id=citizen.id,
                title="Far future",
                due_date=date(2026, 12, 31),
                status=ReminderStatus.SCHEDULED,
            )
        )
    with uow as u:
        due = u.reminders.list_due(date(2026, 7, 1))
    assert [r.title for r in due] == ["Apply soon"]


def test_initialize_is_idempotent(factory: SqliteConnectionFactory) -> None:
    factory.initialize()  # second call must be a no-op
    conn = factory.connect()
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        table_rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        names = {row[0] for row in table_rows}
    finally:
        conn.close()
    assert version == 2  # head migration is 0002_identity
    assert _TABLES <= names


# ── regression tests for the Phase 3 adversarial review findings ─────────────
def test_money_column_rejects_non_inr() -> None:
    """Finding 1: column-stored Money must fail loudly rather than drop currency."""
    with pytest.raises(SerializationError):
        mappers.money_to_paise(Money(amount=Decimal("1.00"), currency="USD"))


def test_migration_rolls_back_on_failure(tmp_path: Path) -> None:
    """Finding 2: a failing migration must leave no partial effects and not bump version."""
    factory = SqliteConnectionFactory(tmp_path / "m.db")
    factory.initialize()  # user_version -> 2 (head)
    bad_dir = tmp_path / "migrations"
    bad_dir.mkdir()
    (bad_dir / "0003_bad.sql").write_text(  # version 3 > head, so it is applied
        "CREATE TABLE temp_a (id TEXT);\nINSERT INTO nonexistent_table VALUES ('x');\n",
        encoding="utf-8",
    )
    conn = factory.connect()
    try:
        with pytest.raises(MigrationError):
            apply_migrations(conn, bad_dir)
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        names = {row[0] for row in rows}
        assert "temp_a" not in names  # first statement rolled back
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2  # version unchanged
    finally:
        conn.close()


def test_eligibility_repo_is_append_only(uow: SqliteUnitOfWork) -> None:
    """Finding 3: the concrete repo must refuse update/delete, not just the port."""
    citizen = CitizenProfile(full_name="Append Only")
    scheme = _scheme(code="APPEND-ONLY")
    with uow:
        uow.citizens.add(citizen)
        uow.schemes.add(scheme)
        result = uow.eligibility_results.add(
            EligibilityResult(
                citizen_id=citizen.id, scheme_id=scheme.id, status=EligibilityStatus.ELIGIBLE
            )
        )
    with uow as u:
        with pytest.raises(RepositoryError):
            u.eligibility_results.update(result)
        with pytest.raises(RepositoryError):
            u.eligibility_results.delete(result.id)


def test_fk_violation_is_repository_error_not_duplicate(uow: SqliteUnitOfWork) -> None:
    """Finding 4: a dangling FK must raise RepositoryError, not DuplicateEntityError."""
    with uow as u, pytest.raises(RepositoryError) as excinfo:
        u.reminders.add(Reminder(citizen_id="no-such-citizen", title="orphan"))
    assert not isinstance(excinfo.value, DuplicateEntityError)


def test_duplicate_scheme_code_raises_duplicate(uow: SqliteUnitOfWork) -> None:
    """Finding 4 (other half): a real uniqueness conflict still maps to DuplicateEntityError."""
    with uow as u:
        u.schemes.add(_scheme(code="DUP"))
        with pytest.raises(DuplicateEntityError):
            u.schemes.add(_scheme(code="DUP"))


def test_latest_for_orders_by_instant_not_string(uow: SqliteUnitOfWork) -> None:
    """Finding 6: ordering must be by true instant even with mixed timezone offsets."""
    citizen = CitizenProfile(full_name="TZ User")
    scheme = _scheme(code="TZ")
    ist = timezone(timedelta(hours=5, minutes=30))
    with uow:
        uow.citizens.add(citizen)
        uow.schemes.add(scheme)
        # Earlier instant (12:00Z) written with a +05:30 offset.
        uow.eligibility_results.add(
            EligibilityResult(
                citizen_id=citizen.id,
                scheme_id=scheme.id,
                status=EligibilityStatus.NEEDS_MORE_INFO,
                evaluated_at=datetime(2026, 1, 1, 17, 30, tzinfo=ist),
            )
        )
        # Later instant (13:00Z) in UTC.
        uow.eligibility_results.add(
            EligibilityResult(
                citizen_id=citizen.id,
                scheme_id=scheme.id,
                status=EligibilityStatus.ELIGIBLE,
                evaluated_at=datetime(2026, 1, 1, 13, 0, tzinfo=UTC),
            )
        )
    with uow as u:
        latest = u.eligibility_results.latest_for(citizen.id, scheme.id)
    assert latest is not None
    assert latest.status == EligibilityStatus.ELIGIBLE
