"""bharatai.common.redaction — PII masking helpers.

Per the v1 privacy posture, sensitive identifiers are masked before they are
stored, logged, or displayed. Full Aadhaar/PAN numbers must never be persisted.
"""
from __future__ import annotations

import re

_AADHAAR_RE = re.compile(r"\b(\d{4})\s?(\d{4})\s?(\d{4})\b")
_PAN_RE = re.compile(r"\b([A-Z]{5})(\d{4})([A-Z])\b")


def mask_aadhaar(value: str) -> str:
    """Mask a 12-digit Aadhaar number, keeping only the last 4 digits."""
    digits = re.sub(r"\D", "", value)
    if len(digits) != 12:
        return "XXXX XXXX XXXX"
    return f"XXXX XXXX {digits[-4:]}"


def aadhaar_last4(value: str) -> str | None:
    """Return the last 4 digits of an Aadhaar number, or None if not 12 digits."""
    digits = re.sub(r"\D", "", value)
    return digits[-4:] if len(digits) == 12 else None


def mask_pan(value: str) -> str:
    """Mask a PAN, revealing only the first two and last characters."""
    v = value.strip().upper()
    if not _PAN_RE.fullmatch(v):
        return "XXXXXXXXXX"
    return f"{v[:2]}XXXXX{v[-1]}"


def redact_pii(text: str) -> str:
    """Redact Aadhaar and PAN patterns from free text (e.g. before logging)."""
    text = _AADHAAR_RE.sub("XXXX XXXX XXXX", text)
    text = _PAN_RE.sub("XXXXXXXXXX", text)
    return text
