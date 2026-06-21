"""bharatai.application.services.audit_service — record and query audit events."""
from __future__ import annotations

from collections.abc import Callable

from bharatai.application.ports.repositories import UnitOfWork
from bharatai.domain.identity import AuditEvent

UowFactory = Callable[[], UnitOfWork]


class AuditService:
    """Records security-relevant actions and reads the recent audit trail."""

    def __init__(self, uow_factory: UowFactory) -> None:
        """Inject the UnitOfWork factory."""
        self._uow_factory = uow_factory

    def record(
        self,
        action: str,
        *,
        actor_id: str | None = None,
        resource: str | None = None,
        success: bool = True,
        detail: str | None = None,
    ) -> None:
        """Append an audit event."""
        with self._uow_factory() as uow:
            uow.audit_events.add(
                AuditEvent(
                    actor_id=actor_id,
                    action=action,
                    resource=resource,
                    success=success,
                    detail=detail,
                )
            )

    def recent(self, limit: int = 100) -> list[AuditEvent]:
        """Return the most recent audit events."""
        with self._uow_factory() as uow:
            return uow.audit_events.list_recent(limit)
