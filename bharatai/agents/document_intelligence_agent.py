"""bharatai.agents.document_intelligence_agent — (4) validate uploaded documents.

Loads each pending document's bytes via an injected FileStore, runs it through the
injected document analyzer (OCR + extraction + validation + scoring), and returns the
validated records, the set of VALID document types, and an overall readiness score.
Per-document failures degrade to warnings — the batch never crashes.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field

from bharatai.agents.base import AgentContext, BaseAgent
from bharatai.application.ports.documents import DocumentAnalyzerPort, FileStorePort
from bharatai.common.logging import get_logger
from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.document import DocumentRecord
from bharatai.domain.enums import DocumentType, DocumentValidationStatus


class DocumentInput(BaseModel):
    """Pending documents to analyze, the owning profile, and the required document set."""

    model_config = ConfigDict(extra="forbid")

    documents: list[DocumentRecord]
    profile: CitizenProfile | None = None
    required_documents: list[DocumentType] = Field(default_factory=list)


class DocumentAnalysisResult(BaseModel):
    """The validated documents, which types are VALID, the readiness score, and warnings."""

    model_config = ConfigDict(extra="forbid")

    documents: list[DocumentRecord]
    readiness_score: int
    validated_doc_types: list[DocumentType] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DocumentIntelligenceAgent(BaseAgent[DocumentInput, DocumentAnalysisResult]):
    """Validates uploaded documents and computes an application-readiness score."""

    name = "document_intelligence"

    def __init__(
        self,
        analyzer: DocumentAnalyzerPort,
        file_store: FileStorePort,
        logger: logging.Logger | None = None,
    ) -> None:
        """Inject the document analyzer, the file store, and a logger."""
        self._analyzer = analyzer
        self._file_store = file_store
        self._logger = logger or get_logger(__name__)

    def run(self, data: DocumentInput, ctx: AgentContext) -> DocumentAnalysisResult:
        """Analyze each document, then score the citizen's overall document readiness."""
        today = ctx.now.date()
        analyzed: list[DocumentRecord] = []
        warnings: list[str] = []
        for record in data.documents:
            if not record.file_path:
                warnings.append(f"document '{record.id}' has no file path; skipped")
                analyzed.append(record)
                continue
            try:
                image = self._file_store.read(record.file_path)
                analyzed.append(
                    self._analyzer.analyze_document(
                        record, image, profile=data.profile, today=today
                    )
                )
            except Exception as exc:  # noqa: BLE001 - degrade per document, never fail the batch
                warnings.append(f"could not analyze document '{record.id}': {exc}")
                self._logger.warning("document analysis failed", exc_info=exc)
                analyzed.append(record)
                continue

        validated = list(
            dict.fromkeys(
                doc.doc_type
                for doc in analyzed
                if doc.validation_status is DocumentValidationStatus.VALID
            )
        )
        readiness = self._analyzer.compute_readiness(analyzed, data.required_documents)
        self._logger.info(
            "analyzed documents",
            extra={"trace_id": ctx.trace_id, "count": len(analyzed), "readiness": readiness},
        )
        return DocumentAnalysisResult(
            documents=analyzed,
            readiness_score=readiness,
            validated_doc_types=validated,
            warnings=warnings,
        )
