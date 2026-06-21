"""bharatai.infrastructure.knowledge.chunking — turn schemes into retrievable chunks.

A scheme is flattened into a single provenance-rich text document, then split into
overlapping windows. The splitter is a deterministic, dependency-free character window
(a LlamaIndex SentenceSplitter can be swapped in for production-grade sentence awareness).
"""
from __future__ import annotations

from bharatai.application.dto import RetrievedChunk
from bharatai.common.logging import get_logger
from bharatai.domain.scheme import Scheme

_logger = get_logger(__name__)
_split_fallback_logged = False


def scheme_to_text(scheme: Scheme) -> str:
    """Flatten a Scheme into a single text document for embedding/retrieval."""
    lines: list[str] = [f"Scheme: {scheme.name}"]
    if scheme.code:
        lines.append(f"Code: {scheme.code}")
    if scheme.department:
        lines.append(f"Department: {scheme.department}")
    if scheme.level:
        lines.append(f"Level: {scheme.level}")
    if scheme.state:
        lines.append(f"State: {scheme.state.value}")
    if scheme.category_tags:
        lines.append(f"Categories: {', '.join(scheme.category_tags)}")
    if scheme.description:
        lines.append(f"Description: {scheme.description}")

    criteria = scheme.eligibility_criteria
    crit_parts: list[str] = []
    if criteria.min_age is not None:
        crit_parts.append(f"minimum age {criteria.min_age}")
    if criteria.max_age is not None:
        crit_parts.append(f"maximum age {criteria.max_age}")
    if criteria.allowed_genders:
        crit_parts.append("genders " + ", ".join(g.value for g in criteria.allowed_genders))
    if criteria.allowed_categories:
        crit_parts.append("categories " + ", ".join(c.value for c in criteria.allowed_categories))
    if criteria.max_annual_income is not None:
        crit_parts.append(f"annual income up to Rs {criteria.max_annual_income.amount}")
    if criteria.allowed_states:
        crit_parts.append("states " + ", ".join(s.value for s in criteria.allowed_states))
    if criteria.residence_types:
        crit_parts.append("residence " + ", ".join(r.value for r in criteria.residence_types))
    if criteria.requires_bpl:
        crit_parts.append("below poverty line")
    if criteria.min_disability_percentage is not None:
        crit_parts.append(f"minimum disability {criteria.min_disability_percentage}%")
    if criteria.required_documents:
        crit_parts.append("documents " + ", ".join(d.value for d in criteria.required_documents))
    if criteria.custom_flags:
        crit_parts.append(
            "flags " + ", ".join(f"{key}={value}" for key, value in criteria.custom_flags.items())
        )
    if crit_parts:
        lines.append("Eligibility: " + "; ".join(crit_parts) + ".")
    if criteria.raw_rules_text:
        lines.append(f"Rules: {criteria.raw_rules_text}")

    for benefit in scheme.benefits:
        amount = f" ({benefit.amount.amount} INR)" if benefit.amount else ""
        freq = f" [{benefit.frequency}]" if benefit.frequency else ""
        lines.append(f"Benefit: {benefit.description}{amount}{freq}")

    if scheme.application_window and (
        scheme.application_window.start or scheme.application_window.end
    ):
        window = scheme.application_window
        start = window.start.isoformat() if window.start else "open"
        end = window.end.isoformat() if window.end else "open"
        lines.append(f"Application window: {start} to {end}")
    if scheme.source_url:
        lines.append(f"Source: {scheme.source_url}")
    if scheme.verified_at:
        lines.append(f"Verified on: {scheme.verified_at.isoformat()}")
    return "\n".join(lines)


def split_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
    """Split text into overlapping fixed-size character windows (deterministic)."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        window = text[start : start + chunk_size].strip()
        if window:
            chunks.append(window)
        if start + chunk_size >= len(text):
            break
        start += chunk_size - overlap
    return chunks


def _split(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text, preferring LlamaIndex's SentenceSplitter, falling back to a pure window."""
    try:
        from llama_index.core.node_parser import SentenceSplitter

        splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
        pieces = [piece.strip() for piece in splitter.split_text(text) if piece.strip()]
        if pieces:
            return pieces
    except Exception as exc:  # noqa: BLE001 - any LlamaIndex/tokenizer failure falls back to pure split
        global _split_fallback_logged
        if not _split_fallback_logged:
            _logger.warning(
                "SentenceSplitter unavailable; using char-window fallback", exc_info=exc
            )
            _split_fallback_logged = True
    return split_text(text, chunk_size, overlap)


def build_chunks(
    schemes: list[Scheme], chunk_size: int = 512, overlap: int = 64
) -> list[RetrievedChunk]:
    """Build provenance-tagged chunks for the ACTIVE schemes (score left at 0.0).

    Inactive (discontinued) schemes are skipped so a stale scheme can never surface as a
    grounded, cited answer.
    """
    records: list[RetrievedChunk] = []
    for scheme in schemes:
        if not scheme.is_active:
            continue
        pieces = _split(scheme_to_text(scheme), chunk_size, overlap)
        for index, piece in enumerate(pieces):
            records.append(
                RetrievedChunk(
                    text=piece,
                    source_id=scheme.id,
                    source_title=scheme.name,
                    source_url=scheme.source_url,
                    chunk_id=f"{scheme.id}:{index}",
                )
            )
    return records
