"""bharatai.bootstrap.testing — wire a container from injected fakes for tests."""
from __future__ import annotations

from bharatai.agents.bureaucracy_translator_agent import BureaucracyTranslatorAgent
from bharatai.agents.citizen_profile_agent import CitizenProfileAgent
from bharatai.agents.document_intelligence_agent import DocumentIntelligenceAgent
from bharatai.agents.eligibility_agent import EligibilityIntelligenceAgent
from bharatai.agents.recommendation_agent import RecommendationAgent
from bharatai.agents.reminder_agent import ReminderDeadlineAgent
from bharatai.agents.scheme_discovery_agent import SchemeDiscoveryAgent
from bharatai.application.ports.documents import DocumentAnalyzerPort, FileStorePort
from bharatai.application.ports.knowledge import KnowledgeBasePort
from bharatai.application.ports.llm import LLMPort
from bharatai.application.ports.repositories import UnitOfWork
from bharatai.application.services.application_service import ApplicationService
from bharatai.application.services.citizen_service import CitizenProfileService
from bharatai.application.services.document_service import DocumentService
from bharatai.application.services.eligibility_service import EligibilityService
from bharatai.application.services.reminder_service import ReminderService
from bharatai.application.services.scheme_service import SchemeService
from bharatai.bootstrap.container import Container
from bharatai.bootstrap.service_bundle import ServiceBundle
from bharatai.config.settings import AppSettings
from bharatai.infrastructure.db.connection import SqliteConnectionFactory
from bharatai.infrastructure.db.unit_of_work import SqliteUnitOfWork
from bharatai.orchestration.registry import GraphDependencies
from bharatai.orchestration.runner import BharatGraphRunner


def build_test_container(
    connection_factory: SqliteConnectionFactory,
    *,
    knowledge: KnowledgeBasePort,
    llm: LLMPort,
    file_store: FileStorePort,
    document_analyzer: DocumentAnalyzerPort,
) -> Container:
    """Wire a Container over a temp DB with injected fakes (no real models)."""
    connection_factory.initialize()
    settings = AppSettings()

    def uow_factory() -> UnitOfWork:
        return SqliteUnitOfWork(connection_factory)

    dependencies = GraphDependencies(
        profile=CitizenProfileAgent(),
        discovery=SchemeDiscoveryAgent(knowledge),
        document=DocumentIntelligenceAgent(analyzer=document_analyzer, file_store=file_store),
        eligibility=EligibilityIntelligenceAgent(llm=llm),
        recommendation=RecommendationAgent(),
        reminder=ReminderDeadlineAgent(),
        translator=BureaucracyTranslatorAgent(llm),
    )
    services = ServiceBundle(
        settings=settings,
        citizens=CitizenProfileService(uow_factory),
        schemes=SchemeService(uow_factory, knowledge),
        documents=DocumentService(uow_factory, file_store),
        reminders=ReminderService(uow_factory),
        eligibility=EligibilityService(uow_factory),
        applications=ApplicationService(uow_factory),
        knowledge=knowledge,
        graph_runner=BharatGraphRunner.from_dependencies(dependencies),
    )
    return Container(settings=settings, connection_factory=connection_factory, services=services)
