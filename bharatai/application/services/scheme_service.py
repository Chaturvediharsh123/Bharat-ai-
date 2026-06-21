"""bharatai.application.services.scheme_service — government scheme use cases."""
from __future__ import annotations

from collections.abc import Callable

from bharatai.application.ports.knowledge import KnowledgeBasePort
from bharatai.application.ports.repositories import UnitOfWork
from bharatai.domain.scheme import Scheme

UowFactory = Callable[[], UnitOfWork]


class SchemeService:
    """Manages the scheme corpus in the DB and (re)builds the knowledge index."""

    def __init__(self, uow_factory: UowFactory, knowledge: KnowledgeBasePort) -> None:
        """Inject the UnitOfWork factory and the knowledge base."""
        self._uow_factory = uow_factory
        self._knowledge = knowledge

    def list_active(self) -> list[Scheme]:
        """Return all active schemes."""
        with self._uow_factory() as uow:
            return uow.schemes.list_active()

    def upsert(self, scheme: Scheme) -> Scheme:
        """Insert or update a scheme (by code when present)."""
        with self._uow_factory() as uow:
            if scheme.code:
                return uow.schemes.upsert_by_code(scheme)
            return uow.schemes.add(scheme)

    def seed(self, schemes: list[Scheme]) -> int:
        """Upsert the given schemes and rebuild the knowledge index from active schemes."""
        with self._uow_factory() as uow:
            for scheme in schemes:
                if scheme.code:
                    uow.schemes.upsert_by_code(scheme)
                else:
                    uow.schemes.add(scheme)
            active = uow.schemes.list_active()
        self._knowledge.rebuild(active)
        return len(active)
