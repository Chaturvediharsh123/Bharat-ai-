"""bharatai.infrastructure.db.repositories.audit_repo — append-only audit log."""
from __future__ import annotations

import sqlite3
from typing import Any

from bharatai.domain.identity import AuditEvent
from bharatai.infrastructure.db import mappers as m
from bharatai.infrastructure.db.repositories._base import SqliteRepository


class SqliteAuditRepository(SqliteRepository[AuditEvent]):
    """Append-only persistence for security audit events."""

    table = "audit_events"

    def _to_row(self, entity: AuditEvent) -> dict[str, Any]:
        return {
            "id": entity.id,
            "actor_id": entity.actor_id,
            "action": entity.action,
            "resource": entity.resource,
            "success": m.bool_to_int(entity.success),
            "detail": entity.detail,
            "occurred_at": m.dt_to_iso(entity.occurred_at),
            "created_at": m.dt_to_iso(entity.created_at),
            "updated_at": m.dt_to_iso(entity.updated_at),
        }

    def _from_row(self, row: sqlite3.Row) -> AuditEvent:
        return AuditEvent(
            id=row["id"],
            actor_id=row["actor_id"],
            action=row["action"],
            resource=row["resource"],
            success=bool(row["success"]),
            detail=row["detail"],
            occurred_at=m.dt_from_iso_req(row["occurred_at"]),
            created_at=m.dt_from_iso_req(row["created_at"]),
            updated_at=m.dt_from_iso_req(row["updated_at"]),
        )

    def list_recent(self, limit: int = 100) -> list[AuditEvent]:
        """Return the most recent audit events (newest first)."""
        rows = self._conn.execute(
            f"SELECT * FROM {self.table} ORDER BY occurred_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def list_by_actor(self, actor_id: str) -> list[AuditEvent]:
        """Return all audit events for an actor, newest first."""
        return self._query("actor_id = ?", (actor_id,), "occurred_at DESC")
