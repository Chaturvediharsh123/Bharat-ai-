"""bharatai.infrastructure.ocr.scoring — confidence and readiness scoring.

ConfidenceScore (0-1) blends OCR confidence with how many key fields were extracted.
ReadinessScore (0-100) measures how complete and valid a citizen's required document set is.
"""
from __future__ import annotations

from bharatai.domain.document import DocumentRecord
from bharatai.domain.enums import DocumentType, DocumentValidationStatus
from bharatai.infrastructure.ocr.field_parsers import ExtractedDocument

# Per document type, the fields whose presence signals a good extraction.
_KEY_FIELDS: dict[DocumentType, tuple[str, ...]] = {
    DocumentType.AADHAAR: ("name", "date_of_birth", "document_number_masked"),
    DocumentType.PAN: ("name", "document_number_masked"),
    DocumentType.INCOME: ("name", "income", "issue_date"),
    DocumentType.DOMICILE: ("name", "issue_date"),
    DocumentType.BONAFIDE: ("name", "issue_date"),
}
_OCR_WEIGHT = 0.6
_FIELD_WEIGHT = 0.4


class ConfidenceScorer:
    """Scores how confident we are in a single document's extraction (0-1)."""

    def score(self, ocr_confidence: float, extracted: ExtractedDocument) -> float:
        """Blend OCR confidence with the fraction of key fields successfully extracted."""
        keys = _KEY_FIELDS.get(extracted.doc_type, ())
        if keys:
            present = sum(1 for field in keys if getattr(extracted, field) is not None)
            field_score = present / len(keys)
        else:
            field_score = 1.0
        blended = _OCR_WEIGHT * ocr_confidence + _FIELD_WEIGHT * field_score
        return round(min(1.0, max(0.0, blended)), 4)


class ReadinessScorer:
    """Scores how ready a citizen's document set is for an application (0-100)."""

    def score(self, records: list[DocumentRecord], required: list[DocumentType]) -> int:
        """Return the percentage of required document types present and VALID."""
        valid_types = {
            record.doc_type
            for record in records
            if record.validation_status is DocumentValidationStatus.VALID
        }
        if required:
            needed = set(required)
            satisfied = len(needed & valid_types)
            return round(100 * satisfied / len(needed))
        if not records:
            return 0
        valid_count = sum(
            1 for r in records if r.validation_status is DocumentValidationStatus.VALID
        )
        return round(100 * valid_count / len(records))
