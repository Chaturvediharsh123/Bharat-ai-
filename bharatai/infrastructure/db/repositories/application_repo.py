"""bharatai.infrastructure.db.repositories.application_repo — application history store."""
from __future__ import annotations

import sqlite3
from typing import Any

from bharatai.domain.application import ApplicationHistoryEntry
from bharatai.domain.enums import ApplicationStatus
from bharatai.infrastructure.db import mappers as m
from bharatai.infrastructure.db.repositories._base import SqliteRepository


class SqliteApplicationHistoryRepository(SqliteRepository[ApplicationHistoryEntry]):
    """Stores a citizen's scheme application records and their statuses."""

    table = "application_history"

    def _to_row(self, entity: ApplicationHistoryEntry) -> dict[str, Any]:
        return {
            "id": entity.id,
            "citizen_id": entity.citizen_id,
            "scheme_id": entity.scheme_id,
            "status": entity.status.value,
            "reference_id": entity.reference_id,
            "notes": entity.notes,
            "submitted_at": m.dt_to_iso(entity.submitted_at),
            "updated_status_at": m.dt_to_iso(entity.updated_status_at),
            "created_at": m.dt_to_iso(entity.created_at),
            "updated_at": m.dt_to_iso(entity.updated_at),
        }

    def _from_row(self, row: sqlite3.Row) -> ApplicationHistoryEntry:
        return ApplicationHistoryEntry(
            id=row["id"],
            citizen_id=row["citizen_id"],
            scheme_id=row["scheme_id"],
            status=ApplicationStatus(row["status"]),
            reference_id=row["reference_id"],
            notes=row["notes"],
            submitted_at=m.dt_from_iso(row["submitted_at"]),
            updated_status_at=m.dt_from_iso(row["updated_status_at"]),
            created_at=m.dt_from_iso_req(row["created_at"]),
            updated_at=m.dt_from_iso_req(row["updated_at"]),
        )

    def list_by_citizen(self, citizen_id: str) -> list[ApplicationHistoryEntry]:
        """Return all application entries for a citizen, newest first."""
        return self._query("citizen_id = ?", (citizen_id,), "created_at DESC")

    def list_by_citizen_and_scheme(
        self, citizen_id: str, scheme_id: str
    ) -> list[ApplicationHistoryEntry]:
        """Return a citizen's application entries for a specific scheme."""
        return self._query(
            "citizen_id = ? AND scheme_id = ?", (citizen_id, scheme_id), "created_at DESC"
        )
