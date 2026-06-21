"""bharatai.infrastructure.db.repositories.scheme_repo — Scheme persistence."""
from __future__ import annotations

import sqlite3
from typing import Any

from bharatai.domain.enums import IndianState
from bharatai.domain.scheme import EligibilityCriteria, Scheme, SchemeBenefit
from bharatai.domain.value_objects import DateRange
from bharatai.infrastructure.db import mappers as m
from bharatai.infrastructure.db.repositories._base import SqliteRepository


class SqliteSchemeRepository(SqliteRepository[Scheme]):
    """Stores government schemes, including provenance fields and structured criteria."""

    table = "schemes"

    def _to_row(self, entity: Scheme) -> dict[str, Any]:
        return {
            "id": entity.id,
            "name": entity.name,
            "code": entity.code,
            "description": entity.description,
            "department": entity.department,
            "level": entity.level,
            "state": entity.state.value if entity.state else None,
            "category_tags_json": m.str_list_to_json(entity.category_tags),
            "eligibility_criteria_json": m.model_to_json(entity.eligibility_criteria),
            "benefits_json": m.models_to_json(list(entity.benefits)),
            "application_window_json": m.model_to_json(entity.application_window),
            "source_url": entity.source_url,
            "verified_at": m.date_to_iso(entity.verified_at),
            "is_active": m.bool_to_int(entity.is_active),
            "created_at": m.dt_to_iso(entity.created_at),
            "updated_at": m.dt_to_iso(entity.updated_at),
        }

    def _from_row(self, row: sqlite3.Row) -> Scheme:
        criteria = m.json_to_model(EligibilityCriteria, row["eligibility_criteria_json"])
        return Scheme(
            id=row["id"],
            name=row["name"],
            code=row["code"],
            description=row["description"],
            department=row["department"],
            level=row["level"],
            state=IndianState(row["state"]) if row["state"] else None,
            category_tags=m.json_to_str_list(row["category_tags_json"]),
            eligibility_criteria=criteria or EligibilityCriteria(),
            benefits=m.json_to_models(SchemeBenefit, row["benefits_json"]),
            application_window=m.json_to_model(DateRange, row["application_window_json"]),
            source_url=row["source_url"],
            verified_at=m.date_from_iso(row["verified_at"]),
            is_active=bool(row["is_active"]),
            created_at=m.dt_from_iso_req(row["created_at"]),
            updated_at=m.dt_from_iso_req(row["updated_at"]),
        )

    def list_active(self) -> list[Scheme]:
        """Return all active schemes, newest first."""
        return self._query("is_active = 1", (), "created_at DESC")

    def get_by_code(self, code: str) -> Scheme | None:
        """Return the scheme with this unique code, or None."""
        return self._query_one("code = ?", (code,))

    def upsert_by_code(self, scheme: Scheme) -> Scheme:
        """Insert a scheme, or update the existing one sharing its code (ingestion)."""
        if scheme.code is None:
            return self.add(scheme)
        existing = self.get_by_code(scheme.code)
        if existing is None:
            return self.add(scheme)
        merged = scheme.model_copy(update={"id": existing.id, "created_at": existing.created_at})
        return self.update(merged)
