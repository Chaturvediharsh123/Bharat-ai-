"""bharatai.application.services.application_service — application-history use cases."""
from __future__ import annotations

from collections.abc import Callable

from bharatai.application.ports.repositories import UnitOfWork
from bharatai.domain.application import ApplicationHistoryEntry

UowFactory = Callable[[], UnitOfWork]


class ApplicationService:
    """Lists and records a citizen's scheme application history."""

    def __init__(self, uow_factory: UowFactory) -> None:
        """Inject the UnitOfWork factory."""
        self._uow_factory = uow_factory

    def list_for(self, citizen_id: str) -> list[ApplicationHistoryEntry]:
        """Return all application entries for a citizen."""
        with self._uow_factory() as uow:
            return uow.applications.list_by_citizen(citizen_id)

    def record(self, entry: ApplicationHistoryEntry) -> ApplicationHistoryEntry:
        """Record a new application entry."""
        with self._uow_factory() as uow:
            return uow.applications.add(entry)
