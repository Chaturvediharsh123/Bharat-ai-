"""bharatai.infrastructure.db.connection — SQLite connections and migrations.

The only module (with the repositories) that imports ``sqlite3``. Connections are
configured for safe concurrent local use (WAL, foreign keys, busy timeout) and the
schema is applied via forward-only migrations gated by ``PRAGMA user_version``.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from bharatai.common.exceptions import MigrationError
from bharatai.common.logging import get_logger

_logger = get_logger(__name__)
_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class SqliteConnectionFactory:
    """Creates configured SQLite connections to a single database file."""

    def __init__(self, db_path: str | Path, busy_timeout_ms: int = 5000) -> None:
        """Store the DB path and ensure its parent directory exists."""
        self._db_path = str(db_path)
        self._busy_timeout_ms = busy_timeout_ms
        if self._db_path != ":memory:":
            Path(self._db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)

    @property
    def db_path(self) -> str:
        """The configured database file path."""
        return self._db_path

    def connect(self) -> sqlite3.Connection:
        """Open a new connection with row access by name and safe PRAGMAs."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute(f"PRAGMA busy_timeout = {int(self._busy_timeout_ms)}")
        except BaseException:
            conn.close()  # never leak the handle if setup fails
            raise
        return conn

    def initialize(self) -> None:
        """Apply any pending migrations to bring the database to the latest version."""
        conn = self.connect()
        try:
            apply_migrations(conn)
        finally:
            conn.close()


def apply_migrations(conn: sqlite3.Connection, migrations_dir: Path = _MIGRATIONS_DIR) -> int:
    """Apply forward-only ``*.sql`` migrations whose version exceeds user_version.

    Returns the resulting schema version. Each migration filename must begin with a
    zero-padded integer version (e.g. ``0001_init.sql``).
    """
    current = int(conn.execute("PRAGMA user_version").fetchone()[0])
    applied_to = current
    # Run each migration as one explicit transaction. executescript() is avoided
    # because it force-commits, which would make a mid-migration failure unrollable.
    conn.isolation_level = None
    for path in sorted(migrations_dir.glob("*.sql")):
        try:
            version = int(path.name.split("_", 1)[0])
        except ValueError as exc:
            raise MigrationError(f"Bad migration filename: {path.name}") from exc
        if version <= current:
            continue
        _logger.info("applying migration", extra={"migration": path.name, "version": version})
        statements = _split_sql_statements(path.read_text(encoding="utf-8"))
        try:
            conn.execute("BEGIN")
            for statement in statements:
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {version}")
            conn.execute("COMMIT")
        except sqlite3.Error as exc:
            conn.execute("ROLLBACK")
            raise MigrationError(f"Migration {path.name} failed: {exc}") from exc
        applied_to = version
    return applied_to


def _split_sql_statements(script: str) -> list[str]:
    """Split a migration script into individual statements.

    Line comments (``--`` to end of line) are stripped first so that semicolons
    inside comments do not split statements; the result is split on ``;``. Migration
    files must therefore use only simple statements (no compound BEGIN..END bodies or
    semicolons inside string literals) and no explicit BEGIN/COMMIT.
    """
    without_comments = "\n".join(line.split("--", 1)[0] for line in script.splitlines())
    return [statement.strip() for statement in without_comments.split(";") if statement.strip()]
