"""bharatai.bootstrap.container — the top-level wired object graph."""
from __future__ import annotations

from dataclasses import dataclass

from bharatai.bootstrap.service_bundle import ServiceBundle
from bharatai.config.settings import AppSettings
from bharatai.infrastructure.db.connection import SqliteConnectionFactory


@dataclass(frozen=True)
class Container:
    """Holds process-wide singletons; ``services`` is what the UI consumes."""

    settings: AppSettings
    connection_factory: SqliteConnectionFactory
    services: ServiceBundle
