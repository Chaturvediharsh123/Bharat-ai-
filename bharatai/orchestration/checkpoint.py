"""bharatai.orchestration.checkpoint — optional SQLite checkpointer factory.

Checkpointing is NOT wired into build_graph by default: the Phase-1 review flagged that
graph state carries PII, so persistence must be enabled deliberately (with redaction).
Kept separate from the application database.
"""
from __future__ import annotations

from typing import Any


def create_sqlite_checkpointer(db_path: str) -> Any:
    """Create a LangGraph SQLite checkpointer (the caller manages its lifecycle)."""
    from langgraph.checkpoint.sqlite import SqliteSaver

    return SqliteSaver.from_conn_string(db_path)
