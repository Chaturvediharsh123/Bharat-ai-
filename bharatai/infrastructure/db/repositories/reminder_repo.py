"""bharatai.infrastructure.db.repositories.reminder_repo — Reminder persistence."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from bharatai.domain.enums import ReminderChannel, ReminderStatus
from bharatai.domain.reminder import Reminder
from bharatai.infrastructure.db import mappers as m
from bharatai.infrastructure.db.repositories._base import SqliteRepository


class SqliteReminderRepository(SqliteRepository[Reminder]):
    """Stores deadline reminders for citizens."""

    table = "reminders"

    def _to_row(self, entity: Reminder) -> dict[str, Any]:
        return {
            "id": entity.id,
            "citizen_id": entity.citizen_id,
            "scheme_id": entity.scheme_id,
            "title": entity.title,
            "description": entity.description,
            "due_date": m.date_to_iso(entity.due_date),
            "remind_at": m.dt_to_iso(entity.remind_at),
            "status": entity.status.value,
            "channel": entity.channel.value,
            "created_at": m.dt_to_iso(entity.created_at),
            "updated_at": m.dt_to_iso(entity.updated_at),
        }

    def _from_row(self, row: sqlite3.Row) -> Reminder:
        return Reminder(
            id=row["id"],
            citizen_id=row["citizen_id"],
            scheme_id=row["scheme_id"],
            title=row["title"],
            description=row["description"],
            due_date=m.date_from_iso(row["due_date"]),
            remind_at=m.dt_from_iso(row["remind_at"]),
            status=ReminderStatus(row["status"]),
            channel=ReminderChannel(row["channel"]),
            created_at=m.dt_from_iso_req(row["created_at"]),
            updated_at=m.dt_from_iso_req(row["updated_at"]),
        )

    def list_by_citizen(self, citizen_id: str) -> list[Reminder]:
        """Return all reminders for a citizen, soonest due first."""
        return self._query("citizen_id = ?", (citizen_id,), "due_date ASC")

    def list_due(self, on_or_before: date) -> list[Reminder]:
        """Return scheduled reminders due on or before a date."""
        return self._query(
            "status = ? AND due_date IS NOT NULL AND due_date <= ?",
            (ReminderStatus.SCHEDULED.value, on_or_before.isoformat()),
            "due_date ASC",
        )
