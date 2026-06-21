"""bharatai.agents.reminder_agent — (7) derive deadline reminders.

Builds Reminder records from scheme application-window deadlines for schemes the citizen is
eligible for and has not yet applied to, computing due dates, lead-time alerts, and status
transitions (SCHEDULED -> DUE -> EXPIRED). Reconciles with existing reminders so a scheme is
never duplicated. Deterministic — all "now" comes from the injected AgentContext clock.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field

from bharatai.agents.base import AgentContext, BaseAgent
from bharatai.common.logging import get_logger
from bharatai.domain.application import ApplicationHistoryEntry
from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.eligibility import EligibilityResult
from bharatai.domain.enums import (
    ApplicationStatus,
    EligibilityStatus,
    ReminderChannel,
    ReminderStatus,
)
from bharatai.domain.reminder import Reminder
from bharatai.domain.scheme import Scheme

_AVAILING = {
    ApplicationStatus.SUBMITTED,
    ApplicationStatus.UNDER_REVIEW,
    ApplicationStatus.APPROVED,
}
_WORTH_REMINDING = {EligibilityStatus.ELIGIBLE, EligibilityStatus.NEEDS_MORE_INFO}
_TERMINAL = {ReminderStatus.DONE, ReminderStatus.CANCELLED, ReminderStatus.SENT}


class ReminderInput(BaseModel):
    """Inputs for planning reminders: schemes, eligibility, applications, prior reminders."""

    model_config = ConfigDict(extra="forbid")

    profile: CitizenProfile
    schemes: list[Scheme]
    eligibility_results: list[EligibilityResult] = Field(default_factory=list)
    applications: list[ApplicationHistoryEntry] = Field(default_factory=list)
    existing_reminders: list[Reminder] = Field(default_factory=list)
    lead_days: int = 7


class ReminderPlan(BaseModel):
    """The reconciled reminder set, split into created/updated, plus a summary."""

    model_config = ConfigDict(extra="forbid")

    reminders: list[Reminder]
    created: list[Reminder] = Field(default_factory=list)
    updated: list[Reminder] = Field(default_factory=list)
    summary: str


class ReminderDeadlineAgent(BaseAgent[ReminderInput, ReminderPlan]):
    """Plans deadline reminders and transitions their status deterministically."""

    name = "reminder_deadline"

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Inject a logger (the agent is otherwise pure domain logic)."""
        self._logger = logger or get_logger(__name__)

    def run(self, data: ReminderInput, ctx: AgentContext) -> ReminderPlan:
        """Create/update reminders for eligible schemes with deadlines; transition existing ones."""
        now = ctx.now
        worth = self._worth_reminding_scheme_ids(data)
        availing = {app.scheme_id for app in data.applications if app.status in _AVAILING}
        existing_by_scheme: dict[str, list[Reminder]] = {}
        for reminder in data.existing_reminders:
            if reminder.scheme_id is not None:
                existing_by_scheme.setdefault(reminder.scheme_id, []).append(reminder)

        reminders: list[Reminder] = []
        created: list[Reminder] = []
        updated: list[Reminder] = []
        handled_schemes: set[str] = set()
        handled_reminders: set[str] = set()

        for scheme in data.schemes:
            deadline = scheme.application_window.end if scheme.application_window else None
            if deadline is None or scheme.id not in worth or scheme.id in availing:
                continue
            if scheme.id in handled_schemes:  # ignore duplicate scheme ids within the batch
                continue
            handled_schemes.add(scheme.id)
            desired = self._build(scheme, deadline, data, now)
            group = existing_by_scheme.get(scheme.id, [])
            if not group:
                reminders.append(desired)
                created.append(desired)
                continue
            # Update the active reminder to the new deadline; preserve the rest (incl. terminal).
            primary = next((r for r in group if r.status not in _TERMINAL), group[0])
            for existing in group:
                handled_reminders.add(existing.id)
                outcome = (
                    self._merge(existing, desired, now)
                    if existing is primary
                    else self._transition(existing, now)
                )
                reminders.append(outcome)
                if outcome is not existing:
                    updated.append(outcome)

        for reminder in data.existing_reminders:
            if reminder.id in handled_reminders:
                continue
            transitioned = self._transition(reminder, now)
            reminders.append(transitioned)
            if transitioned is not reminder:
                updated.append(transitioned)

        self._logger.info(
            "planned reminders",
            # NOTE: 'created' is a reserved LogRecord attribute — use distinct keys.
            extra={
                "trace_id": ctx.trace_id,
                "created_count": len(created),
                "updated_count": len(updated),
            },
        )
        return ReminderPlan(
            reminders=reminders,
            created=created,
            updated=updated,
            summary=self._summary(reminders, created, updated),
        )

    @staticmethod
    def _worth_reminding_scheme_ids(data: ReminderInput) -> set[str]:
        # Collapse append-only eligibility history to the latest status per scheme; the
        # sort (with id tie-break) makes the winner deterministic even on equal timestamps.
        latest: dict[str, EligibilityResult] = {}
        for result in sorted(data.eligibility_results, key=lambda r: (r.evaluated_at, r.id)):
            latest[result.scheme_id] = result
        return {sid for sid, res in latest.items() if res.status in _WORTH_REMINDING}

    def _build(
        self, scheme: Scheme, deadline: date, data: ReminderInput, now: datetime
    ) -> Reminder:
        remind_at = self._remind_at(deadline, data.lead_days)
        return Reminder(
            citizen_id=data.profile.id,
            scheme_id=scheme.id,
            title=f"Apply for {scheme.name}",
            description=(
                f"The application window for {scheme.name} closes on {deadline.isoformat()}."
            ),
            due_date=deadline,
            remind_at=remind_at,
            status=self._status(deadline, remind_at, now),
            channel=ReminderChannel.IN_APP,
        )

    @staticmethod
    def _remind_at(deadline: date, lead_days: int) -> datetime:
        remind_date = deadline - timedelta(days=max(0, lead_days))
        return datetime(remind_date.year, remind_date.month, remind_date.day, tzinfo=UTC)

    @staticmethod
    def _status(deadline: date, remind_at: datetime | None, now: datetime) -> ReminderStatus:
        if deadline < now.date():
            return ReminderStatus.EXPIRED
        if remind_at is not None and remind_at <= now:
            return ReminderStatus.DUE
        return ReminderStatus.SCHEDULED

    def _merge(self, existing: Reminder, desired: Reminder, now: datetime) -> Reminder:
        if existing.status in _TERMINAL:
            return existing
        return existing.model_copy(
            update={
                "title": desired.title,
                "description": desired.description,
                "due_date": desired.due_date,
                "remind_at": desired.remind_at,
                "status": desired.status,
                "updated_at": now,
            }
        )

    def _transition(self, reminder: Reminder, now: datetime) -> Reminder:
        if reminder.status in _TERMINAL or reminder.due_date is None:
            return reminder
        new_status = self._status(reminder.due_date, reminder.remind_at, now)
        if new_status == reminder.status:
            return reminder
        return reminder.model_copy(update={"status": new_status, "updated_at": now})

    @staticmethod
    def _summary(
        reminders: list[Reminder], created: list[Reminder], updated: list[Reminder]
    ) -> str:
        due = sum(1 for r in reminders if r.status is ReminderStatus.DUE)
        expired = sum(1 for r in reminders if r.status is ReminderStatus.EXPIRED)
        return (
            f"{len(created)} new and {len(updated)} updated reminder(s); "
            f"{due} due now, {expired} past deadline."
        )
