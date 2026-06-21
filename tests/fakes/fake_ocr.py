"""Fake OcrPort for offline tests: returns a canned OcrResult built from text."""
from __future__ import annotations

from bharatai.domain.value_objects import OcrField, OcrResult


def ocr_from_text(text: str, confidence: float = 0.95) -> OcrResult:
    """Build an OcrResult from plain text, one OcrField per non-empty line."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    fields = [
        OcrField(name=f"line_{index}", value=line, confidence=confidence)
        for index, line in enumerate(lines)
    ]
    return OcrResult(raw_text=text, fields=fields, confidence=confidence, engine="fake")


class FakeOcr:
    """Returns a preset OcrResult regardless of input image."""

    def __init__(self, result: OcrResult | str) -> None:
        self._result = result if isinstance(result, OcrResult) else ocr_from_text(result)

    def extract_text(self, image: bytes) -> OcrResult:
        return self._result
