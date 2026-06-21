"""Slow integration test: the real PaddleOCR adapter runs and returns an OcrResult.

Marked ``slow`` (excluded from the default gate) because it loads PaddleOCR models.
Run with: pytest -m slow
"""
from __future__ import annotations

import io

import pytest

pytest.importorskip("paddleocr")
pytest.importorskip("PIL")

from PIL import Image, ImageDraw  # noqa: E402

from bharatai.domain.value_objects import OcrResult  # noqa: E402
from bharatai.infrastructure.ocr.paddle_adapter import PaddleOcrAdapter  # noqa: E402


@pytest.mark.slow
def test_paddle_adapter_returns_ocr_result() -> None:
    image = Image.new("RGB", (480, 100), "white")
    ImageDraw.Draw(image).text((20, 35), "PAN ABCDE1234F", fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    result = PaddleOcrAdapter().extract_text(buffer.getvalue())
    assert isinstance(result, OcrResult)
    assert result.engine == "paddleocr"
    assert 0.0 <= result.confidence <= 1.0
