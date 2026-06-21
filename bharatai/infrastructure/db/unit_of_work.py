"""bharatai.infrastructure.db.unit_of_work — transactional repository aggregate.

A UnitOfWork owns one connection and one transaction and exposes every repository.
Used as a context manager: it commits on clean exit and rolls back on exception.
"""
from __future__ import annotations

import sqlite3

from bharatai.application.ports.repositories import (
    ApplicationHistoryRepository,
    AuditRepository,
    CitizenProfileRepository,
    DocumentRepository,
    EligibilityResultRepository,
    ReminderRepository,
    SchemeRepository,
    UserRepository,
)
from bharatai.common.exceptions import RepositoryError
from bharatai.infrastructure.db.connection import SqliteConnectionFactory
from bharatai.infrastructure.db.repositories.application_repo import (
    SqliteApplicationHistoryRepository,
)
from bharatai.infrastructure.db.repositories.audit_repo import SqliteAuditRepository
from bharatai.infrastructure.db.repositories.citizen_repo import SqliteCitizenProfileRepository
from bharatai.infrastructure.db.repositories.document_repo import SqliteDocumentRepository
from bharatai.infrastructure.db.repositories.eligibility_repo import (
    SqliteEligibilityResultRepository,
)
from bharatai.infrastructure.db.repositories.reminder_repo import SqliteReminderRepository
from bharatai.infrastructure.db.repositories.scheme_repo import SqliteSchemeRepository
from bharatai.infrastructure.db.repositories.user_repo import SqliteUserRepository


class SqliteUnitOfWork:
    """Opens one connection/transaction and exposes all six repositories."""

    # Typed as the ports (not the concrete classes) so SqliteUnitOfWork structurally
    # satisfies the UnitOfWork protocol whose attributes are the port interfaces.
    citizens: CitizenProfileRepository
    schemes: SchemeRepository
    eligibility_results: EligibilityResultRepository
    documents: DocumentRepository
    reminders: ReminderRepository
    applications: ApplicationHistoryRepository
    users: UserRepository
    audit_events: AuditRepository

    def __init__(self, factory: SqliteConnectionFactory) -> None:
        """Store the connection factory; the connection opens on ``__enter__``."""
        self._factory = factory
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> SqliteUnitOfWork:
        """Open a connection and bind a fresh set of repositories to it."""
        conn = self._factory.connect()
        self._conn = conn
        self.citizens = SqliteCitizenProfileRepository(conn)
        self.schemes = SqliteSchemeRepository(conn)
        self.eligibility_results = SqliteEligibilityResultRepository(conn)
        self.documents = SqliteDocumentRepository(conn)
        self.reminders = SqliteReminderRepository(conn)
        self.applications = SqliteApplicationHistoryRepository(conn)
        self.users = SqliteUserRepository(conn)
        self.audit_events = SqliteAuditRepository(conn)
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Commit on clean exit, roll back on error, then close the connection."""
        conn = self._conn
        if conn is None:
            return
        try:
            if exc_type is not None:
                conn.rollback()
            else:
                conn.commit()
        finally:
            conn.close()
            self._conn = None

    @property
    def connection(self) -> sqlite3.Connection:
        """The active connection (raises if used outside a ``with`` block)."""
        if self._conn is None:
            raise RepositoryError("UnitOfWork accessed outside of its context manager")
        return self._conn

    def commit(self) -> None:
        """Commit the current transaction without closing the UnitOfWork."""
        self.connection.commit()

    def rollback(self) -> None:
        """Roll back the current transaction without closing the UnitOfWork."""
        self.connection.rollback()
