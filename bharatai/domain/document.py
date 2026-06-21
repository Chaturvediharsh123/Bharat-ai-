"""bharatai.domain.document — the DocumentRecord aggregate (upload + OCR + validation)."""
from __future__ import annotations

from datetime import date

from pydantic import Field

from bharatai.domain.base import Entity
from bharatai.domain.enums import DocumentType, DocumentValidationStatus
from bharatai.domain.value_objects import OcrResult


class DocumentRecord(Entity):
    """An uploaded citizen document, its OCR output, and its validation outcome.

    Only ``file_path`` (not bytes) is held; extracted identifiers are stored MASKED.
    """

    citizen_id: str
    doc_type: DocumentType
    file_path: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    file_size_bytes: int | None = Field(default=None, ge=0)
    checksum_sha256: str | None = None
    ocr_result: OcrResult | None = None
    extracted_name: str | None = None
    extracted_dob: date | None = None
    extracted_document_number: str | None = None  # MASKED
    issue_date: date | None = None
    expiry_date: date | None = None
    validation_status: DocumentValidationStatus = DocumentValidationStatus.PENDING
    validation_errors: list[str] = Field(default_factory=list)
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
