"""bharatai.domain.reminder — the Reminder aggregate."""
from __future__ import annotations

from datetime import date, datetime

from bharatai.domain.base import Entity
from bharatai.domain.enums import ReminderChannel, ReminderStatus


class Reminder(Entity):
    """A deadline reminder, optionally tied to a scheme."""

    citizen_id: str
    scheme_id: str | None = None
    title: str
    description: str | None = None
    due_date: date | None = None
    remind_at: datetime | None = None
    status: ReminderStatus = ReminderStatus.SCHEDULED
    channel: ReminderChannel = ReminderChannel.IN_APP
