"""Tests for document validation, scoring, and the DocumentIntelligenceService."""
from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from bharatai.domain.citizen import CitizenProfile
from bharatai.domain.document import DocumentRecord
from bharatai.domain.enums import DocumentType, DocumentValidationStatus
from bharatai.domain.value_objects import OcrResult
from bharatai.infrastructure.ocr.field_parsers import ExtractedDocument
from bharatai.infrastructure.ocr.scoring import ConfidenceScorer, ReadinessScorer
from bharatai.infrastructure.ocr.service import DocumentIntelligenceService
from bharatai.infrastructure.ocr.validators import DocumentValidator
from tests.fakes.fake_ocr import FakeOcr

_TODAY = date(2026, 6, 20)


def _ocr(confidence: float = 0.95) -> OcrResult:
    return OcrResult(raw_text="x", confidence=confidence, engine="fake")


def _pan(name: str = "Rahul Sharma", *, valid: bool = True) -> ExtractedDocument:
    return ExtractedDocument(
        doc_type=DocumentType.PAN,
        name=name,
        document_number_masked="ABXXXXXF" if valid else None,
        number_valid=valid,
    )


def test_validator_unreadable_on_low_confidence() -> None:
    report = DocumentValidator().validate(_pan(), _ocr(0.2), None, _TODAY)
    assert report.status is DocumentValidationStatus.UNREADABLE


def test_validator_invalid_on_bad_format() -> None:
    report = DocumentValidator().validate(_pan(valid=False), _ocr(), None, _TODAY)
    assert report.status is DocumentValidationStatus.INVALID


def test_validator_expired_certificate() -> None:
    extracted = ExtractedDocument(
        doc_type=DocumentType.INCOME, name="Ramesh", expiry_date=date(2025, 1, 1)
    )
    report = DocumentValidator().validate(extracted, _ocr(), None, _TODAY)
    assert report.status is DocumentValidationStatus.EXPIRED


def test_validator_name_mismatch() -> None:
    profile = CitizenProfile(full_name="Priya Singh")
    report = DocumentValidator().validate(_pan("Rahul Sharma"), _ocr(), profile, _TODAY)
    assert report.status is DocumentValidationStatus.MISMATCH


def test_validator_valid_when_matching() -> None:
    profile = CitizenProfile(full_name="Rahul Sharma")
    report = DocumentValidator().validate(_pan("Rahul Sharma"), _ocr(), profile, _TODAY)
    assert report.status is DocumentValidationStatus.VALID


def test_validator_single_common_surname_is_mismatch() -> None:
    profile = CitizenProfile(full_name="Harpreet Singh")
    report = DocumentValidator().validate(_pan("Singh"), _ocr(), profile, _TODAY)
    assert report.status is DocumentValidationStatus.MISMATCH


def test_service_round_trip_rejects_out_of_range_confidence() -> None:
    record = DocumentRecord(citizen_id="c", doc_type=DocumentType.PAN)
    with pytest.raises(ValidationError):
        DocumentRecord.model_validate({**record.model_dump(), "confidence_score": 9.9})


def test_confidence_scorer_blends_ocr_and_fields() -> None:
    score = ConfidenceScorer().score(0.9, _pan())
    assert score == 0.94  # 0.6*0.9 + 0.4*1.0 (both key fields present)


def test_readiness_scorer_over_required_set() -> None:
    records = [
        DocumentRecord(
            citizen_id="c",
            doc_type=DocumentType.AADHAAR,
            validation_status=DocumentValidationStatus.VALID,
        ),
        DocumentRecord(
            citizen_id="c",
            doc_type=DocumentType.PAN,
            validation_status=DocumentValidationStatus.INVALID,
        ),
    ]
    required = [DocumentType.AADHAAR, DocumentType.PAN, DocumentType.INCOME]
    assert ReadinessScorer().score(records, required) == 33


def test_service_analyze_document() -> None:
    record = DocumentRecord(citizen_id="c", doc_type=DocumentType.PAN)
    service = DocumentIntelligenceService(
        FakeOcr("Income Tax Department\nName: Rahul Sharma\nPAN ABCDE1234F")
    )
    profile = CitizenProfile(full_name="Rahul Sharma")
    out = service.analyze_document(record, b"image-bytes", profile=profile, today=_TODAY)
    assert out.validation_status is DocumentValidationStatus.VALID
    assert out.extracted_name == "Rahul Sharma"
    assert out.extracted_document_number == "ABXXXXXF"
    assert out.ocr_result is not None
    assert 0.0 <= (out.confidence_score or 0.0) <= 1.0


def test_service_redacts_full_id_from_stored_ocr() -> None:
    service = DocumentIntelligenceService(
        FakeOcr("Government of India\nName: Asha Devi\n2341 2345 6789\nFemale")
    )
    record = DocumentRecord(citizen_id="c", doc_type=DocumentType.AADHAAR)
    out = service.analyze_document(record, b"image-bytes", today=_TODAY)
    dump = out.model_dump_json()
    assert "2341 2345 6789" not in dump  # full Aadhaar must not survive in the stored OCR text
    assert "234123456789" not in dump


def test_service_compute_readiness() -> None:
    service = DocumentIntelligenceService(FakeOcr("x"))
    records = [
        DocumentRecord(
            citizen_id="c",
            doc_type=DocumentType.AADHAAR,
            validation_status=DocumentValidationStatus.VALID,
        )
    ]
    assert service.compute_readiness(records, [DocumentType.AADHAAR]) == 100
