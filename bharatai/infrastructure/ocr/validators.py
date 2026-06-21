"""bharatai.infrastructure.ocr.validators — document validation rules.

Turns an ExtractedDocument (+ the citizen profile) into a single canonical
DocumentValidationStatus with human-readable error messages. Status precedence:
UNREADABLE > INVALID > EXPIRED > MISMATCH > VALID.
"""
from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.enums import DocumentType, DocumentValidationStatus
from bharatai.domain.value_objects import OcrResult
from bharatai.infrastructure.ocr.field_parsers import ExtractedDocument

_ID_DOCUMENTS = {DocumentType.AADHAAR, DocumentType.PAN}
_WORD = re.compile(r"[a-z]+")


class ValidationReport(BaseModel):
    """The outcome of validating one document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: DocumentValidationStatus
    errors: list[str] = Field(default_factory=list)


def _name_tokens(name: str) -> set[str]:
    return set(_WORD.findall(name.lower()))


def _names_match(extracted: str, profile_name: str) -> bool:
    left, right = _name_tokens(extracted), _name_tokens(profile_name)
    if not left or not right:
        return False
    if left == right:
        return True
    # A one-sided subset only counts as a match when the smaller name fully overlaps
    # AND shares at least two tokens — a lone common surname/first name is not enough.
    common = left & right
    smaller = min(len(left), len(right))
    return len(common) == smaller and smaller >= 2


class DocumentValidator:
    """Validates extracted document fields against format, expiry, and the profile."""

    def __init__(self, min_ocr_confidence: float = 0.5) -> None:
        """Set the OCR confidence below which a document is treated as unreadable."""
        self._min_ocr_confidence = min_ocr_confidence

    def validate(
        self,
        extracted: ExtractedDocument,
        ocr: OcrResult,
        profile: CitizenProfile | None,
        today: date,
    ) -> ValidationReport:
        """Return the canonical validation status and the errors that drove it."""
        errors: list[str] = []

        if ocr.confidence < self._min_ocr_confidence:
            errors.append("document text could not be read confidently")
            return ValidationReport(status=DocumentValidationStatus.UNREADABLE, errors=errors)

        requires_number = extracted.doc_type in _ID_DOCUMENTS
        missing_required = extracted.name is None or (
            requires_number and extracted.document_number_masked is None
        )
        if extracted.name is None:
            errors.append("name not found")
        if requires_number and extracted.document_number_masked is None:
            errors.append("document number not found")
        if extracted.number_valid is False:
            errors.append("invalid document number format or checksum")

        expired = extracted.expiry_date is not None and extracted.expiry_date < today
        mismatch = (
            profile is not None
            and profile.full_name is not None
            and extracted.name is not None
            and not _names_match(extracted.name, profile.full_name)
        )

        if extracted.number_valid is False or missing_required:
            status = DocumentValidationStatus.INVALID
        elif expired:
            errors.append("certificate has expired")
            status = DocumentValidationStatus.EXPIRED
        elif mismatch:
            errors.append("name does not match the citizen profile")
            status = DocumentValidationStatus.MISMATCH
        else:
            status = DocumentValidationStatus.VALID

        return ValidationReport(status=status, errors=errors)
