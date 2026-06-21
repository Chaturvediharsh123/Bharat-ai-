"""bharatai.infrastructure.db.repositories._base — generic SQLite repository.

Factors out the CRUD boilerplate so each concrete repository only defines its
table name and its row<->domain mapping (DRY + single-responsibility).
"""
from __future__ import annotations

import sqlite3
from typing import Any, Generic, TypeVar

from bharatai.common.exceptions import (
    DuplicateEntityError,
    EntityNotFoundError,
    RepositoryError,
)
from bharatai.domain.base import Entity

T = TypeVar("T", bound=Entity)


class SqliteRepository(Generic[T]):
    """Base class providing insert/update/get/delete/query over one table.

    Table and column names are class-controlled constants (never user input), so the
    f-string SQL composed here is not an injection surface.
    """

    table: str = ""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Bind the repository to an open connection (owned by the UnitOfWork)."""
        self._conn = conn

    # -- mapping hooks (implemented by subclasses) --------------------------------
    def _to_row(self, entity: T) -> dict[str, Any]:
        raise NotImplementedError

    def _from_row(self, row: sqlite3.Row) -> T:
        raise NotImplementedError

    # -- write --------------------------------------------------------------------
    def _insert(self, entity: T) -> None:
        row = self._to_row(entity)
        columns = ", ".join(row)
        placeholders = ", ".join(["?"] * len(row))
        sql = f"INSERT INTO {self.table} ({columns}) VALUES ({placeholders})"
        try:
            self._conn.execute(sql, tuple(row.values()))
        except sqlite3.IntegrityError as exc:
            message = str(exc).lower()
            if "unique" in message or "primary key" in message:
                raise DuplicateEntityError(f"{self.table}: {exc}") from exc
            # NOT NULL / CHECK / FOREIGN KEY violations are not duplicates.
            raise RepositoryError(f"{self.table} integrity error: {exc}") from exc
        except sqlite3.Error as exc:
            raise RepositoryError(f"{self.table} insert failed: {exc}") from exc

    def _update_row(self, entity: T) -> None:
        row = self._to_row(entity)
        assignments = ", ".join(f"{column} = ?" for column in row if column != "id")
        values: list[Any] = [value for column, value in row.items() if column != "id"]
        values.append(row["id"])
        sql = f"UPDATE {self.table} SET {assignments} WHERE id = ?"
        try:
            cursor = self._conn.execute(sql, values)
        except sqlite3.Error as exc:
            raise RepositoryError(f"{self.table} update failed: {exc}") from exc
        if cursor.rowcount == 0:
            raise EntityNotFoundError(f"{self.table} id not found: {row['id']}")

    def add(self, entity: T) -> T:
        """Insert a new entity and return it."""
        self._insert(entity)
        return entity

    def update(self, entity: T) -> T:
        """Bump ``updated_at`` and persist changes to an existing entity."""
        entity.touch()
        self._update_row(entity)
        return entity

    # -- read ---------------------------------------------------------------------
    def get(self, entity_id: str) -> T | None:
        """Return the entity with this id, or None."""
        row = self._conn.execute(
            f"SELECT * FROM {self.table} WHERE id = ?", (entity_id,)
        ).fetchone()
        return self._from_row(row) if row is not None else None

    def delete(self, entity_id: str) -> bool:
        """Delete by id; return True if a row was removed."""
        cursor = self._conn.execute(f"DELETE FROM {self.table} WHERE id = ?", (entity_id,))
        return cursor.rowcount > 0

    def _query(
        self, where: str = "", params: tuple[Any, ...] = (), order_by: str = ""
    ) -> list[T]:
        sql = f"SELECT * FROM {self.table}"
        if where:
            sql += f" WHERE {where}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        rows = self._conn.execute(sql, params).fetchall()
        return [self._from_row(row) for row in rows]

    def _query_one(self, where: str, params: tuple[Any, ...], order_by: str = "") -> T | None:
        results = self._query(where, params, order_by)
        return results[0] if results else None
