"""bharatai.application.ports.ocr — the OCR Protocol (port).

The document pipeline depends on this abstraction; the PaddleOCR adapter implements it.
The boundary type is the domain ``OcrResult`` so no OCR library type ever leaks upward.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from bharatai.domain.value_objects import OcrResult


@runtime_checkable
class OcrPort(Protocol):
    """Extract text from a document image."""

    def extract_text(self, image: bytes) -> OcrResult: ...
