"""bharatai.infrastructure.db.repositories.eligibility_repo — EligibilityResult store.

Append-only: every evaluation is a new row, preserving decision history.
"""
from __future__ import annotations

import sqlite3
from typing import Any, NoReturn

from bharatai.common.exceptions import RepositoryError
from bharatai.domain.eligibility import CriterionEvaluation, EligibilityResult
from bharatai.domain.enums import EligibilityStatus
from bharatai.infrastructure.db import mappers as m
from bharatai.infrastructure.db.repositories._base import SqliteRepository


class SqliteEligibilityResultRepository(SqliteRepository[EligibilityResult]):
    """Append-only persistence for eligibility decisions."""

    table = "eligibility_results"

    def update(self, entity: EligibilityResult) -> NoReturn:
        """Reject mutation: eligibility history is append-only."""
        raise RepositoryError("eligibility_results is append-only; insert a new evaluation instead")

    def delete(self, entity_id: str) -> NoReturn:
        """Reject deletion: eligibility history is append-only."""
        raise RepositoryError("eligibility_results is append-only; rows cannot be deleted")

    def _to_row(self, entity: EligibilityResult) -> dict[str, Any]:
        return {
            "id": entity.id,
            "citizen_id": entity.citizen_id,
            "scheme_id": entity.scheme_id,
            "status": entity.status.value,
            "score": entity.score,
            "confidence": entity.confidence,
            "evaluations_json": m.models_to_json(list(entity.evaluations)),
            "missing_profile_fields_json": m.str_list_to_json(entity.missing_profile_fields),
            "explanation": entity.explanation,
            "evaluated_at": m.dt_to_iso(entity.evaluated_at),
            "created_at": m.dt_to_iso(entity.created_at),
            "updated_at": m.dt_to_iso(entity.updated_at),
        }

    def _from_row(self, row: sqlite3.Row) -> EligibilityResult:
        return EligibilityResult(
            id=row["id"],
            citizen_id=row["citizen_id"],
            scheme_id=row["scheme_id"],
            status=EligibilityStatus(row["status"]),
            score=row["score"] if row["score"] is not None else 0.0,
            confidence=row["confidence"] if row["confidence"] is not None else 0.0,
            evaluations=m.json_to_models(CriterionEvaluation, row["evaluations_json"]),
            missing_profile_fields=m.json_to_str_list(row["missing_profile_fields_json"]),
            explanation=row["explanation"],
            evaluated_at=m.dt_from_iso_req(row["evaluated_at"]),
            created_at=m.dt_from_iso_req(row["created_at"]),
            updated_at=m.dt_from_iso_req(row["updated_at"]),
        )

    def list_by_citizen(self, citizen_id: str) -> list[EligibilityResult]:
        """Return all eligibility results for a citizen, newest evaluation first."""
        return self._query("citizen_id = ?", (citizen_id,), "evaluated_at DESC")

    def latest_for(self, citizen_id: str, scheme_id: str) -> EligibilityResult | None:
        """Return the most recent evaluation for a citizen + scheme pair."""
        return self._query_one(
            "citizen_id = ? AND scheme_id = ?", (citizen_id, scheme_id), "evaluated_at DESC"
        )
