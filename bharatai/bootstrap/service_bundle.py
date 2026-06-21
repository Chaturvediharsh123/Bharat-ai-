"""bharatai.bootstrap.service_bundle — the wired services + graph handed to the UI."""
from __future__ import annotations

from dataclasses import dataclass

from bharatai.application.ports.knowledge import KnowledgeBasePort
from bharatai.application.services.application_service import ApplicationService
from bharatai.application.services.citizen_service import CitizenProfileService
from bharatai.application.services.document_service import DocumentService
from bharatai.application.services.eligibility_service import EligibilityService
from bharatai.application.services.reminder_service import ReminderService
from bharatai.application.services.scheme_service import SchemeService
from bharatai.config.settings import AppSettings
from bharatai.orchestration.runner import BharatGraphRunner


@dataclass(frozen=True)
class ServiceBundle:
    """All application services + the compiled graph runner, ready for the UI."""

    settings: AppSettings
    citizens: CitizenProfileService
    schemes: SchemeService
    documents: DocumentService
    reminders: ReminderService
    eligibility: EligibilityService
    applications: ApplicationService
    knowledge: KnowledgeBasePort
    graph_runner: BharatGraphRunner
