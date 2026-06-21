"""bharatai.application.ports.documents — ports for the document-intelligence agent.

The Document agent depends on these abstractions; the infrastructure FileStore and the
DocumentIntelligenceService implement them structurally, so the agent never imports OCR
or storage code directly.
"""
from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.document import DocumentRecord
from bharatai.domain.enums import DocumentType


@runtime_checkable
class FileStorePort(Protocol):
    """Stores and reads uploaded-document bytes."""

    def save(self, data: bytes, *, suffix: str = "") -> str: ...
    def read(self, file_path: str) -> bytes: ...


@runtime_checkable
class DocumentAnalyzerPort(Protocol):
    """Runs OCR + extraction + validation + scoring for a document."""

    def analyze_document(
        self,
        record: DocumentRecord,
        image: bytes,
        *,
        profile: CitizenProfile | None = None,
        today: date | None = None,
    ) -> DocumentRecord: ...

    def compute_readiness(
        self, records: list[DocumentRecord], required: list[DocumentType]
    ) -> int: ...
