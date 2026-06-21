"""Tests for the ReminderDeadlineAgent (deterministic deadline reminders)."""
from __future__ import annotations

from datetime import UTC, date, datetime

from bharatai.agents.base import AgentContext
from bharatai.agents.reminder_agent import ReminderDeadlineAgent, ReminderInput
from bharatai.domain.application import ApplicationHistoryEntry
from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.eligibility import EligibilityResult
from bharatai.domain.enums import (
    ApplicationStatus,
    EligibilityStatus,
    ReminderStatus,
)
from bharatai.domain.reminder import Reminder
from bharatai.domain.scheme import Scheme
from bharatai.domain.value_objects import DateRange

_NOW = datetime(2026, 6, 20, tzinfo=UTC)
_CTX = AgentContext(trace_id="trace-1", now=_NOW)
_AGENT = ReminderDeadlineAgent()


def _scheme(name: str, deadline: date | None) -> Scheme:
    window = DateRange(end=deadline) if deadline else None
    return Scheme(name=name, application_window=window)


def _elig(scheme_id: str, status: EligibilityStatus) -> EligibilityResult:
    return EligibilityResult(citizen_id="c", scheme_id=scheme_id, status=status)


def _run(scheme: Scheme, status: EligibilityStatus, **kwargs: object) -> object:
    return _AGENT.run(
        ReminderInput(
            profile=CitizenProfile(),
            schemes=[scheme],
            eligibility_results=[_elig(scheme.id, status)],
            **kwargs,  # type: ignore[arg-type]
        ),
        _CTX,
    )


def test_creates_scheduled_reminder() -> None:
    scheme = _scheme("PM-KISAN", date(2026, 12, 31))
    plan = _AGENT.run(
        ReminderInput(
            profile=CitizenProfile(),
            schemes=[scheme],
            eligibility_results=[_elig(scheme.id, EligibilityStatus.ELIGIBLE)],
        ),
        _CTX,
    )
    assert len(plan.created) == 1
    reminder = plan.created[0]
    assert reminder.scheme_id == scheme.id
    assert reminder.due_date == date(2026, 12, 31)
    assert reminder.remind_at == datetime(2026, 12, 24, tzinfo=UTC)  # 7-day lead
    assert reminder.status is ReminderStatus.SCHEDULED


def test_due_when_within_lead_window() -> None:
    scheme = _scheme("Soon", date(2026, 6, 22))  # 2 days away, lead 7
    plan = _AGENT.run(
        ReminderInput(
            profile=CitizenProfile(),
            schemes=[scheme],
            eligibility_results=[_elig(scheme.id, EligibilityStatus.ELIGIBLE)],
        ),
        _CTX,
    )
    assert plan.created[0].status is ReminderStatus.DUE


def test_expired_when_deadline_passed() -> None:
    scheme = _scheme("Past", date(2026, 6, 1))
    plan = _AGENT.run(
        ReminderInput(
            profile=CitizenProfile(),
            schemes=[scheme],
            eligibility_results=[_elig(scheme.id, EligibilityStatus.ELIGIBLE)],
        ),
        _CTX,
    )
    assert plan.created[0].status is ReminderStatus.EXPIRED


def test_updates_existing_reminder_without_duplicating() -> None:
    scheme = _scheme("PM-KISAN", date(2026, 12, 31))
    existing = Reminder(
        citizen_id="c",
        scheme_id=scheme.id,
        title="old",
        due_date=date(2026, 1, 1),
        status=ReminderStatus.EXPIRED,
    )
    plan = _AGENT.run(
        ReminderInput(
            profile=CitizenProfile(),
            schemes=[scheme],
            eligibility_results=[_elig(scheme.id, EligibilityStatus.ELIGIBLE)],
            existing_reminders=[existing],
        ),
        _CTX,
    )
    assert plan.created == []
    assert len(plan.updated) == 1
    assert len(plan.reminders) == 1  # not duplicated
    assert plan.updated[0].id == existing.id  # same entity
    assert plan.updated[0].due_date == date(2026, 12, 31)
    assert plan.updated[0].status is ReminderStatus.SCHEDULED


def test_skips_scheme_already_applied() -> None:
    scheme = _scheme("PMAY", date(2026, 12, 31))
    plan = _AGENT.run(
        ReminderInput(
            profile=CitizenProfile(),
            schemes=[scheme],
            eligibility_results=[_elig(scheme.id, EligibilityStatus.ELIGIBLE)],
            applications=[
                ApplicationHistoryEntry(
                    citizen_id="c", scheme_id=scheme.id, status=ApplicationStatus.SUBMITTED
                )
            ],
        ),
        _CTX,
    )
    assert plan.reminders == []


def test_skips_not_eligible_and_no_deadline() -> None:
    not_eligible = _run(_scheme("NE", date(2026, 12, 31)), EligibilityStatus.NOT_ELIGIBLE)
    assert not_eligible.reminders == []  # type: ignore[attr-defined]
    no_deadline = _run(_scheme("ND", None), EligibilityStatus.ELIGIBLE)
    assert no_deadline.reminders == []  # type: ignore[attr-defined]


def test_preserves_terminal_and_updates_active_for_same_scheme() -> None:
    scheme = _scheme("PM-KISAN", date(2026, 12, 31))
    done = Reminder(
        citizen_id="c",
        scheme_id=scheme.id,
        title="done",
        due_date=date(2026, 1, 1),
        status=ReminderStatus.DONE,
    )
    active = Reminder(
        citizen_id="c",
        scheme_id=scheme.id,
        title="active",
        due_date=date(2026, 3, 1),
        status=ReminderStatus.SCHEDULED,
    )
    plan = _AGENT.run(
        ReminderInput(
            profile=CitizenProfile(),
            schemes=[scheme],
            eligibility_results=[_elig(scheme.id, EligibilityStatus.ELIGIBLE)],
            existing_reminders=[done, active],
        ),
        _CTX,
    )
    by_id = {r.id: r for r in plan.reminders}
    assert len(plan.reminders) == 2  # neither existing reminder is dropped
    assert by_id[done.id].status is ReminderStatus.DONE  # terminal preserved
    assert by_id[active.id].due_date == date(2026, 12, 31)  # active updated to the new deadline
    assert by_id[active.id].status is ReminderStatus.SCHEDULED


def test_deduplicates_duplicate_scheme_ids() -> None:
    scheme = _scheme("PM-KISAN", date(2026, 12, 31))
    plan = _AGENT.run(
        ReminderInput(
            profile=CitizenProfile(),
            schemes=[scheme, scheme],  # same scheme id twice
            eligibility_results=[_elig(scheme.id, EligibilityStatus.ELIGIBLE)],
        ),
        _CTX,
    )
    assert len(plan.reminders) == 1
    assert len(plan.created) == 1


def test_transition_none_remind_at_keeps_future_scheduled() -> None:
    future = Reminder(
        citizen_id="c",
        scheme_id="ghost-a",
        title="f",
        due_date=date(2026, 12, 31),
        status=ReminderStatus.SCHEDULED,
    )
    past = Reminder(
        citizen_id="c",
        scheme_id="ghost-b",
        title="p",
        due_date=date(2026, 1, 1),
        status=ReminderStatus.SCHEDULED,
    )
    plan = _AGENT.run(
        ReminderInput(profile=CitizenProfile(), schemes=[], existing_reminders=[future, past]),
        _CTX,
    )
    by_id = {r.id: r for r in plan.reminders}
    assert by_id[future.id].status is ReminderStatus.SCHEDULED  # far-future stays scheduled
    assert by_id[past.id].status is ReminderStatus.EXPIRED


def test_transitions_standalone_existing_reminder() -> None:
    existing = Reminder(
        citizen_id="c",
        scheme_id="ghost-scheme",
        title="old",
        due_date=date(2026, 1, 1),
        remind_at=datetime(2025, 12, 25, tzinfo=UTC),
        status=ReminderStatus.SCHEDULED,
    )
    plan = _AGENT.run(
        ReminderInput(profile=CitizenProfile(), schemes=[], existing_reminders=[existing]),
        _CTX,
    )
    assert len(plan.updated) == 1
    assert plan.updated[0].id == existing.id
    assert plan.updated[0].status is ReminderStatus.EXPIRED
