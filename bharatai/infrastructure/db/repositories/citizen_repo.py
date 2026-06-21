"""bharatai.infrastructure.db.repositories.citizen_repo — CitizenProfile persistence."""
from __future__ import annotations

import sqlite3
from typing import Any

from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.enums import Category, Gender, IndianState, MaritalStatus
from bharatai.domain.value_objects import Address
from bharatai.infrastructure.db import mappers as m
from bharatai.infrastructure.db.repositories._base import SqliteRepository


class SqliteCitizenProfileRepository(SqliteRepository[CitizenProfile]):
    """Stores citizen profiles; denormalizes address state/district for indexing."""

    table = "citizen_profiles"

    def _to_row(self, entity: CitizenProfile) -> dict[str, Any]:
        addr = entity.address
        return {
            "id": entity.id,
            "full_name": entity.full_name,
            "date_of_birth": m.date_to_iso(entity.date_of_birth),
            "gender": entity.gender.value if entity.gender else None,
            "category": entity.category.value if entity.category else None,
            "marital_status": entity.marital_status.value if entity.marital_status else None,
            "annual_income_paise": m.money_to_paise(entity.annual_income),
            "occupation": entity.occupation,
            "is_bpl": m.bool_to_int(entity.is_bpl),
            "disability_status": m.bool_to_int(entity.disability_status),
            "disability_percentage": entity.disability_percentage,
            "family_size": entity.family_size,
            "address_json": m.model_to_json(entity.address),
            "state": addr.state.value if addr and addr.state else None,
            "district": addr.district if addr else None,
            "aadhaar_last4": entity.aadhaar_last4,
            "pan_masked": entity.pan_masked,
            "mobile": entity.mobile,
            "languages_json": m.str_list_to_json(entity.languages),
            "created_at": m.dt_to_iso(entity.created_at),
            "updated_at": m.dt_to_iso(entity.updated_at),
        }

    def _from_row(self, row: sqlite3.Row) -> CitizenProfile:
        return CitizenProfile(
            id=row["id"],
            full_name=row["full_name"],
            date_of_birth=m.date_from_iso(row["date_of_birth"]),
            gender=Gender(row["gender"]) if row["gender"] else None,
            category=Category(row["category"]) if row["category"] else None,
            marital_status=MaritalStatus(row["marital_status"]) if row["marital_status"] else None,
            annual_income=m.money_from_paise(row["annual_income_paise"]),
            occupation=row["occupation"],
            is_bpl=m.int_to_bool(row["is_bpl"]),
            disability_status=bool(row["disability_status"]),
            disability_percentage=row["disability_percentage"],
            family_size=row["family_size"],
            address=m.json_to_model(Address, row["address_json"]),
            aadhaar_last4=row["aadhaar_last4"],
            pan_masked=row["pan_masked"],
            mobile=row["mobile"],
            languages=m.json_to_str_list(row["languages_json"]),
            created_at=m.dt_from_iso_req(row["created_at"]),
            updated_at=m.dt_from_iso_req(row["updated_at"]),
        )

    def list_all(self) -> list[CitizenProfile]:
        """Return every citizen profile, newest first."""
        return self._query(order_by="created_at DESC")

    def find_by_state(self, state: IndianState) -> list[CitizenProfile]:
        """Return profiles whose (denormalized) state matches."""
        return self._query("state = ?", (state.value,), "created_at DESC")
