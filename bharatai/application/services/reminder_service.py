"""bharatai.application.services.reminder_service — reminder persistence use cases."""
from __future__ import annotations

from collections.abc import Callable

from bharatai.application.ports.repositories import UnitOfWork
from bharatai.domain.reminder import Reminder

UowFactory = Callable[[], UnitOfWork]


class ReminderService:
    """Lists reminders and persists a reminder plan (created + updated)."""

    def __init__(self, uow_factory: UowFactory) -> None:
        """Inject the UnitOfWork factory."""
        self._uow_factory = uow_factory

    def list_for(self, citizen_id: str) -> list[Reminder]:
        """Return all reminders for a citizen, soonest due first."""
        with self._uow_factory() as uow:
            return uow.reminders.list_by_citizen(citizen_id)

    def save_plan(self, created: list[Reminder], updated: list[Reminder]) -> None:
        """Persist newly-created and updated reminders."""
        with self._uow_factory() as uow:
            for reminder in created:
                uow.reminders.add(reminder)
            for reminder in updated:
                if uow.reminders.get(reminder.id) is None:
                    uow.reminders.add(reminder)
                else:
                    uow.reminders.update(reminder)
