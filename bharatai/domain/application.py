"""bharatai.domain.application — the ApplicationHistoryEntry aggregate."""
from __future__ import annotations

from datetime import datetime

from bharatai.domain.base import Entity
from bharatai.domain.enums import ApplicationStatus


class ApplicationHistoryEntry(Entity):
    """A record of a citizen's application to a scheme and its current status."""

    citizen_id: str
    scheme_id: str
    status: ApplicationStatus = ApplicationStatus.NOT_STARTED
    reference_id: str | None = None
    notes: str | None = None
    submitted_at: datetime | None = None
    updated_status_at: datetime | None = None
