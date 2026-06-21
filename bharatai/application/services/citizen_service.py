"""bharatai.application.services.citizen_service — citizen profile use cases."""
from __future__ import annotations

from collections.abc import Callable

from bharatai.application.ports.repositories import UnitOfWork
from bharatai.domain.citizen import CitizenProfile

UowFactory = Callable[[], UnitOfWork]


class CitizenProfileService:
    """Persists and retrieves citizen profiles via an injected UnitOfWork factory."""

    def __init__(self, uow_factory: UowFactory) -> None:
        """Inject the UnitOfWork factory."""
        self._uow_factory = uow_factory

    def save(self, profile: CitizenProfile) -> CitizenProfile:
        """Insert or update a profile (commit on clean exit)."""
        with self._uow_factory() as uow:
            if uow.citizens.get(profile.id) is None:
                return uow.citizens.add(profile)
            return uow.citizens.update(profile)

    def get(self, citizen_id: str) -> CitizenProfile | None:
        """Return a profile by id, or None."""
        with self._uow_factory() as uow:
            return uow.citizens.get(citizen_id)

    def list_all(self) -> list[CitizenProfile]:
        """Return all citizen profiles."""
        with self._uow_factory() as uow:
            return uow.citizens.list_all()
