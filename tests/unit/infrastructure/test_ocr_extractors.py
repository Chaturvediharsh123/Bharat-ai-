"""Tests for the per-document-type field extractors."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from bharatai.domain.value_objects import Money
from bharatai.infrastructure.ocr.field_parsers import (
    AadhaarExtractor,
    ExtractorRegistry,
    IncomeCertificateExtractor,
    PanExtractor,
)
from bharatai.infrastructure.ocr.parsing import verhoeff_checksum
from tests.fakes.fake_ocr import ocr_from_text


def test_pan_extractor() -> None:
    ocr = ocr_from_text("INCOME TAX DEPARTMENT\nName: Rahul Sharma\nPAN ABCDE1234F")
    result = PanExtractor().parse(ocr)
    assert result.name == "Rahul Sharma"
    assert result.document_number_masked == "ABXXXXXF"
    assert result.number_valid is True


def test_aadhaar_extractor_masks_and_validates() -> None:
    base = "23456789012"
    full = base + str(verhoeff_checksum(base))
    grouped = f"{full[:4]} {full[4:8]} {full[8:]}"
    ocr = ocr_from_text(
        f"Government of India\nName: Asha Devi\nDOB: 01/06/1990\nFemale\n{grouped}"
    )
    result = AadhaarExtractor().parse(ocr)
    assert result.name == "Asha Devi"
    assert result.date_of_birth == date(1990, 6, 1)
    assert result.gender == "female"
    assert result.number_valid is True
    assert result.document_number_masked == f"XXXX XXXX {full[-4:]}"


def test_income_certificate_extractor() -> None:
    ocr = ocr_from_text(
        "Income Certificate\n"
        "Name: Ramesh Kumar\n"
        "Date of Issue: 15/04/2025\n"
        "Annual Income: Rs. 2,50,000\n"
        "Valid up to: 31/03/2026"
    )
    result = IncomeCertificateExtractor().parse(ocr)
    assert result.name == "Ramesh Kumar"
    assert result.income == Money(amount=Decimal("250000"))
    assert result.issue_date == date(2025, 4, 15)
    assert result.expiry_date == date(2026, 3, 31)


def test_income_issue_date_not_confused_with_dob() -> None:
    ocr = ocr_from_text(
        "Name: Ramesh\n"
        "Date of Birth: 12/03/1985\n"
        "Annual Income: Rs. 2,00,000\n"
        "Date of Issue: 10/01/2025"
    )
    result = IncomeCertificateExtractor().parse(ocr)
    assert result.issue_date == date(2025, 1, 10)


def test_pan_name_skips_surname_line() -> None:
    ocr = ocr_from_text("Surname: Sharma\nName: Ravi Kumar\nPAN ABCDE1234F")
    result = PanExtractor().parse(ocr)
    assert result.name == "Ravi Kumar"


def test_registry_resolves_all_types() -> None:
    from bharatai.domain.enums import DocumentType

    registry = ExtractorRegistry()
    for doc_type in DocumentType:
        assert registry.get(doc_type).doc_type is doc_type
