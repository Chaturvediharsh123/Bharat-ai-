"""bharatai.infrastructure.db.repositories.user_repo — User persistence."""
from __future__ import annotations

import sqlite3
from typing import Any

from bharatai.domain.identity import Role, User, UserStatus
from bharatai.infrastructure.db import mappers as m
from bharatai.infrastructure.db.repositories._base import SqliteRepository


class SqliteUserRepository(SqliteRepository[User]):
    """Stores user accounts (email-unique)."""

    table = "users"

    def _to_row(self, entity: User) -> dict[str, Any]:
        return {
            "id": entity.id,
            "email": entity.email,
            "role": entity.role.value,
            "password_hash": entity.password_hash,
            "status": entity.status.value,
            "full_name": entity.full_name,
            "phone": entity.phone,
            "citizen_id": entity.citizen_id,
            "created_at": m.dt_to_iso(entity.created_at),
            "updated_at": m.dt_to_iso(entity.updated_at),
        }

    def _from_row(self, row: sqlite3.Row) -> User:
        return User(
            id=row["id"],
            email=row["email"],
            role=Role(row["role"]),
            password_hash=row["password_hash"],
            status=UserStatus(row["status"]),
            full_name=row["full_name"],
            phone=row["phone"],
            citizen_id=row["citizen_id"],
            created_at=m.dt_from_iso_req(row["created_at"]),
            updated_at=m.dt_from_iso_req(row["updated_at"]),
        )

    def get_by_email(self, email: str) -> User | None:
        """Return the user with this email, or None."""
        return self._query_one("email = ?", (email,))

    def list_all(self) -> list[User]:
        """Return all users, newest first."""
        return self._query(order_by="created_at DESC")
