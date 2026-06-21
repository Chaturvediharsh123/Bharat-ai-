"""bharatai.infrastructure.ocr.paddle_adapter — OcrPort backed by PaddleOCR.

The only place PaddleOCR / Pillow / numpy types appear; they are imported lazily so the
module loads without those heavy dependencies installed. Output is the domain OcrResult.
"""
from __future__ import annotations

import io
from typing import Any

from bharatai.domain.value_objects import OcrField, OcrResult


class PaddleOcrAdapter:
    """OcrPort implementation using a lazily-initialized PaddleOCR engine."""

    def __init__(
        self, lang: str = "en", use_gpu: bool = False, enable_mkldnn: bool = False
    ) -> None:
        """Store engine config; the PaddleOCR model loads on first use.

        ``enable_mkldnn`` defaults to False: some paddlepaddle CPU builds crash in the
        oneDNN kernel, and disabling it is the portable choice for local deployment.
        """
        self._lang = lang
        self._use_gpu = use_gpu
        self._enable_mkldnn = enable_mkldnn
        self._engine: Any = None

    def _ensure_engine(self) -> Any:
        if self._engine is None:
            if not self._enable_mkldnn:
                try:
                    import paddle

                    paddle.set_flags({"FLAGS_use_mkldnn": False})
                except Exception:  # noqa: BLE001 - best effort; the PaddleOCR flag is the real switch
                    pass
            from paddleocr import PaddleOCR

            self._engine = PaddleOCR(lang=self._lang, enable_mkldnn=self._enable_mkldnn)
        return self._engine

    def extract_text(self, image: bytes) -> OcrResult:
        """Run OCR on raw image bytes and return a domain OcrResult."""
        import numpy as np
        from PIL import Image

        engine = self._ensure_engine()
        array = np.asarray(Image.open(io.BytesIO(image)).convert("RGB"))
        predict = getattr(engine, "predict", None)
        raw = predict(array) if callable(predict) else engine.ocr(array)
        texts, confidences = self._parse_results(raw)

        fields = [
            OcrField(name=f"line_{index}", value=text, confidence=confidence)
            for index, (text, confidence) in enumerate(zip(texts, confidences, strict=True))
        ]
        mean = sum(confidences) / len(confidences) if confidences else 0.0
        return OcrResult(
            raw_text="\n".join(texts),
            fields=fields,
            confidence=mean,
            engine="paddleocr",
            language=self._lang,
        )

    @staticmethod
    def _parse_results(raw: Any) -> tuple[list[str], list[float]]:
        """Parse PaddleOCR output across 2.x (list of boxes) and 3.x (dict results)."""
        texts: list[str] = []
        confidences: list[float] = []
        for result in raw or []:
            rec_texts = result.get("rec_texts") if hasattr(result, "get") else None
            if rec_texts is not None:  # PaddleOCR 3.x OCRResult (dict-like)
                rec_scores = result.get("rec_scores") or []
                for index, text in enumerate(rec_texts):
                    score = float(rec_scores[index]) if index < len(rec_scores) else 1.0
                    texts.append(str(text))
                    confidences.append(score)
            elif isinstance(result, list):  # PaddleOCR 2.x [[box, (text, score)], ...]
                for entry in result:
                    try:
                        texts.append(str(entry[1][0]))
                        confidences.append(float(entry[1][1]))
                    except (IndexError, TypeError):
                        continue
        return texts, confidences
