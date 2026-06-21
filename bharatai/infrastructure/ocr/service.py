"""bharatai.infrastructure.ocr.service — the document-intelligence pipeline facade.

Composes OCR -> field extraction -> validation -> scoring into one call that returns an
updated domain DocumentRecord. It performs no persistence (the agent layer persists).
"""
from __future__ import annotations

from datetime import date

from bharatai.application.ports.ocr import OcrPort
from bharatai.common.redaction import redact_pii
from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.document import DocumentRecord
from bharatai.domain.enums import DocumentType
from bharatai.infrastructure.ocr.field_parsers import ExtractorRegistry
from bharatai.infrastructure.ocr.scoring import ConfidenceScorer, ReadinessScorer
from bharatai.infrastructure.ocr.validators import DocumentValidator


class DocumentIntelligenceService:
    """Runs OCR, extraction, validation, and scoring for citizen documents."""

    def __init__(
        self,
        ocr: OcrPort,
        *,
        registry: ExtractorRegistry | None = None,
        validator: DocumentValidator | None = None,
        confidence_scorer: ConfidenceScorer | None = None,
        readiness_scorer: ReadinessScorer | None = None,
    ) -> None:
        """Inject the OCR port and (optionally) the extraction/validation/scoring strategies."""
        self._ocr = ocr
        self._registry = registry or ExtractorRegistry()
        self._validator = validator or DocumentValidator()
        self._confidence = confidence_scorer or ConfidenceScorer()
        self._readiness = readiness_scorer or ReadinessScorer()

    def analyze_document(
        self,
        record: DocumentRecord,
        image: bytes,
        *,
        profile: CitizenProfile | None = None,
        today: date | None = None,
    ) -> DocumentRecord:
        """Run the full pipeline and return an updated copy of the DocumentRecord."""
        ocr_result = self._ocr.extract_text(image)
        extracted = self._registry.get(record.doc_type).parse(ocr_result)
        report = self._validator.validate(extracted, ocr_result, profile, today or date.today())
        confidence = self._confidence.score(ocr_result.confidence, extracted)
        # Store a PII-redacted copy of the OCR result (the full number was extracted above,
        # but must never be persisted in raw_text/fields).
        safe_ocr = ocr_result.model_copy(
            update={
                "raw_text": redact_pii(ocr_result.raw_text),
                "fields": [
                    field.model_copy(update={"value": redact_pii(field.value)})
                    for field in ocr_result.fields
                ],
            }
        )
        update = {
            "ocr_result": safe_ocr,
            "extracted_name": extracted.name,
            "extracted_dob": extracted.date_of_birth,
            "extracted_document_number": extracted.document_number_masked,
            "issue_date": extracted.issue_date,
            "expiry_date": extracted.expiry_date,
            "validation_status": report.status,
            "validation_errors": report.errors,
            "confidence_score": confidence,
        }
        # model_validate (not model_copy) re-runs field validators, so an out-of-range
        # confidence or non-enum status can never be silently persisted.
        return DocumentRecord.model_validate({**record.model_dump(), **update})

    def compute_readiness(
        self, records: list[DocumentRecord], required: list[DocumentType]
    ) -> int:
        """Return a 0-100 readiness score for a citizen's document set."""
        return self._readiness.score(records, required)
