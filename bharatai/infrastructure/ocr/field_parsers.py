"""bharatai.infrastructure.ocr.field_parsers — per-document-type field extraction.

A Strategy pattern: one DocumentExtractor per DocumentType turns a raw OcrResult into a
typed, MASKED ExtractedDocument. Identifier numbers are never stored in full.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import date
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from bharatai.common.exceptions import InfrastructureError
from bharatai.common.redaction import mask_aadhaar, mask_pan
from bharatai.domain.enums import DocumentType
from bharatai.domain.value_objects import Money, OcrResult
from bharatai.infrastructure.ocr.parsing import (
    find_aadhaar,
    find_pan,
    parse_date,
    parse_inr_amount,
    verhoeff_validate,
)

_NON_NAME = re.compile(r"[^A-Za-z .]")
_DATE_TOKEN = re.compile(r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}")
_RELATION = ("father", "husband", "guardian", "mother")


class ExtractedDocument(BaseModel):
    """Typed, masked fields extracted from a single document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_type: DocumentType
    name: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    document_number_masked: str | None = None
    number_valid: bool | None = None
    income: Money | None = None
    issue_date: date | None = None
    expiry_date: date | None = None


def _clean_name(value: str) -> str | None:
    cleaned = _NON_NAME.sub(" ", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.title() if cleaned else None


def _find_name(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        low = line.lower()
        match = re.search(r"\bname\b", low)
        if (
            match
            and "surname" not in low
            and "username" not in low
            and not any(rel in low for rel in _RELATION)
        ):
            after = line[match.end() :].lstrip(" :-").strip()
            candidate = after or (lines[index + 1] if index + 1 < len(lines) else "")
            name = _clean_name(candidate)
            if name:
                return name
    return None


def _value_after_label(text: str, labels: tuple[str, ...]) -> str | None:
    # Try the most specific label first; the generic "date" label only matches as a
    # standalone word and skips birth/validity/application lines.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for label in labels:
        for index, line in enumerate(lines):
            low = line.lower()
            if label == "date":
                match = re.search(r"(?<![a-z])date(?![a-z])", low)
                if not match or any(
                    word in low for word in ("birth", "dob", "valid", "application")
                ):
                    continue
                position = match.start()
            elif label in low:
                position = low.index(label)
            else:
                continue
            after = line[position + len(label) :].lstrip(" :-").strip()
            if after:
                return after
            if index + 1 < len(lines):
                return lines[index + 1]
    return None


def _find_labeled_date(text: str, labels: tuple[str, ...]) -> date | None:
    raw = _value_after_label(text, labels)
    if not raw:
        return None
    token = _DATE_TOKEN.search(raw)
    return parse_date(token.group(0) if token else raw)


def _find_dob(text: str) -> date | None:
    return _find_labeled_date(text, ("date of birth", "dob", "d.o.b", "year of birth", "yob"))


def _find_gender(text: str) -> str | None:
    low = text.lower()
    for gender in ("transgender", "female", "male"):
        if re.search(rf"\b{gender}\b", low):
            return gender
    return None


def _find_income(text: str) -> Money | None:
    for line in text.splitlines():
        low = line.lower()
        if "income" in low and re.search(r"rs|inr|₹|lakh|lac|crore", low):
            amount = parse_inr_amount(line)
            if amount is not None:
                return Money(amount=amount)
    return None


class DocumentExtractor(ABC):
    """Base class for per-document-type extractors."""

    doc_type: ClassVar[DocumentType]

    @abstractmethod
    def parse(self, ocr: OcrResult) -> ExtractedDocument:
        """Parse an OcrResult into an ExtractedDocument."""


class AadhaarExtractor(DocumentExtractor):
    """Extracts and Verhoeff-validates an Aadhaar card."""

    doc_type = DocumentType.AADHAAR

    def parse(self, ocr: OcrResult) -> ExtractedDocument:
        """Parse the OCR result into typed, masked fields."""
        text = ocr.raw_text
        number = find_aadhaar(text)
        return ExtractedDocument(
            doc_type=self.doc_type,
            name=_find_name(text),
            date_of_birth=_find_dob(text),
            gender=_find_gender(text),
            document_number_masked=mask_aadhaar(number) if number else None,
            number_valid=verhoeff_validate(number) if number else None,
        )


class PanExtractor(DocumentExtractor):
    """Extracts and format-validates a PAN card."""

    doc_type = DocumentType.PAN

    def parse(self, ocr: OcrResult) -> ExtractedDocument:
        """Parse the OCR result into typed, masked fields."""
        text = ocr.raw_text
        number = find_pan(text)
        return ExtractedDocument(
            doc_type=self.doc_type,
            name=_find_name(text),
            date_of_birth=_find_dob(text),
            document_number_masked=mask_pan(number) if number else None,
            number_valid=number is not None,
        )


class IncomeCertificateExtractor(DocumentExtractor):
    """Extracts the income amount and validity from an income certificate."""

    doc_type = DocumentType.INCOME

    def parse(self, ocr: OcrResult) -> ExtractedDocument:
        """Parse the OCR result into typed, masked fields."""
        text = ocr.raw_text
        return ExtractedDocument(
            doc_type=self.doc_type,
            name=_find_name(text),
            income=_find_income(text),
            issue_date=_find_labeled_date(text, ("date of issue", "issued on", "date")),
            expiry_date=_find_labeled_date(text, ("valid up to", "valid until", "valid till")),
        )


class DomicileCertificateExtractor(DocumentExtractor):
    """Extracts name and validity from a domicile certificate."""

    doc_type = DocumentType.DOMICILE

    def parse(self, ocr: OcrResult) -> ExtractedDocument:
        """Parse the OCR result into typed, masked fields."""
        text = ocr.raw_text
        return ExtractedDocument(
            doc_type=self.doc_type,
            name=_find_name(text),
            issue_date=_find_labeled_date(text, ("date of issue", "issued on", "date")),
            expiry_date=_find_labeled_date(text, ("valid up to", "valid until", "valid till")),
        )


class BonafideCertificateExtractor(DocumentExtractor):
    """Extracts name and validity from a bonafide certificate."""

    doc_type = DocumentType.BONAFIDE

    def parse(self, ocr: OcrResult) -> ExtractedDocument:
        """Parse the OCR result into typed, masked fields."""
        text = ocr.raw_text
        return ExtractedDocument(
            doc_type=self.doc_type,
            name=_find_name(text),
            issue_date=_find_labeled_date(text, ("date of issue", "issued on", "date")),
            expiry_date=_find_labeled_date(text, ("valid up to", "valid until", "valid till")),
        )


class ExtractorRegistry:
    """Resolves the DocumentExtractor for a DocumentType."""

    def __init__(self, extractors: list[DocumentExtractor] | None = None) -> None:
        """Build the registry from the default extractors (or an override list)."""
        chosen = extractors or [
            AadhaarExtractor(),
            PanExtractor(),
            IncomeCertificateExtractor(),
            DomicileCertificateExtractor(),
            BonafideCertificateExtractor(),
        ]
        self._by_type: dict[DocumentType, DocumentExtractor] = {e.doc_type: e for e in chosen}

    def get(self, doc_type: DocumentType) -> DocumentExtractor:
        """Return the extractor for a document type (raises if unsupported)."""
        try:
            return self._by_type[doc_type]
        except KeyError as exc:
            raise InfrastructureError(f"no extractor registered for {doc_type}") from exc
