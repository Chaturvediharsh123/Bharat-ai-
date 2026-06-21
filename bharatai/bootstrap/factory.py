"""bharatai.bootstrap.factory — wire the production object graph from settings.

This is the composition root: the only place that constructs concrete adapters and injects
them into services and agents. Heavy adapters (Ollama/PaddleOCR/embeddings) load their models
lazily, so building the container is cheap — the models load on first use.
"""
from __future__ import annotations

from bharatai.agents.bureaucracy_translator_agent import BureaucracyTranslatorAgent
from bharatai.agents.citizen_profile_agent import CitizenProfileAgent
from bharatai.agents.document_intelligence_agent import DocumentIntelligenceAgent
from bharatai.agents.eligibility_agent import EligibilityIntelligenceAgent
from bharatai.agents.recommendation_agent import RecommendationAgent
from bharatai.agents.reminder_agent import ReminderDeadlineAgent
from bharatai.agents.scheme_discovery_agent import SchemeDiscoveryAgent
from bharatai.application.ports.repositories import UnitOfWork
from bharatai.application.services.application_service import ApplicationService
from bharatai.application.services.citizen_service import CitizenProfileService
from bharatai.application.services.document_service import DocumentService
from bharatai.application.services.eligibility_service import EligibilityService
from bharatai.application.services.reminder_service import ReminderService
from bharatai.application.services.scheme_service import SchemeService
from bharatai.bootstrap.container import Container
from bharatai.bootstrap.service_bundle import ServiceBundle
from bharatai.common.logging import configure_logging
from bharatai.config.settings import AppSettings
from bharatai.infrastructure.db.connection import SqliteConnectionFactory
from bharatai.infrastructure.db.unit_of_work import SqliteUnitOfWork
from bharatai.infrastructure.knowledge.llamaindex_kb import LlamaIndexFaissKnowledgeBase
from bharatai.infrastructure.llm.caching import CachingLLM
from bharatai.infrastructure.llm.embeddings import SentenceTransformerEmbedding
from bharatai.infrastructure.llm.ollama_client import OllamaLLM
from bharatai.infrastructure.ocr.paddle_adapter import PaddleOcrAdapter
from bharatai.infrastructure.ocr.service import DocumentIntelligenceService
from bharatai.infrastructure.storage.file_store import FileStore
from bharatai.orchestration.registry import GraphDependencies
from bharatai.orchestration.runner import BharatGraphRunner


def build_container(settings: AppSettings) -> Container:
    """Construct and wire the full production container from settings."""
    configure_logging(settings.log_level)
    connection_factory = SqliteConnectionFactory(
        settings.db.sqlite_path, settings.db.busy_timeout_ms
    )
    connection_factory.initialize()

    def uow_factory() -> UnitOfWork:
        return SqliteUnitOfWork(connection_factory)

    # Cache deterministic completions so repeated explanations/simplifications are free.
    llm = CachingLLM(
        OllamaLLM(settings.llm.base_url, settings.llm.default_model, settings.llm.timeout_s)
    )
    embedding = SentenceTransformerEmbedding(
        settings.embedding.model_name, settings.embedding.device
    )
    knowledge = LlamaIndexFaissKnowledgeBase(
        llm=llm, embedding=embedding, settings=settings.knowledge
    )
    file_store = FileStore(settings.ocr.upload_dir, settings.ocr.max_file_mb * 1_000_000)
    analyzer = DocumentIntelligenceService(
        PaddleOcrAdapter(lang=settings.ocr.lang, use_gpu=settings.ocr.use_gpu)
    )

    dependencies = GraphDependencies(
        profile=CitizenProfileAgent(),
        discovery=SchemeDiscoveryAgent(knowledge),
        document=DocumentIntelligenceAgent(analyzer=analyzer, file_store=file_store),
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
