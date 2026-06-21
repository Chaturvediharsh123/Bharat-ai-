"""Tests for scheme-to-text flattening and chunk splitting."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from bharatai.domain.enums import Gender, ResidenceType
from bharatai.domain.scheme import EligibilityCriteria, Scheme, SchemeBenefit
from bharatai.domain.value_objects import Money
from bharatai.infrastructure.knowledge.chunking import build_chunks, scheme_to_text, split_text


def _scheme() -> Scheme:
    return Scheme(
        name="PM-KISAN",
        code="PM-KISAN",
        description="Income support for farmers.",
        source_url="https://pmkisan.gov.in",
        eligibility_criteria=EligibilityCriteria(
            max_annual_income=Money(amount=Decimal("200000.00"))
        ),
        benefits=[
            SchemeBenefit(
                description="Rs 6000 per year",
                amount=Money(amount=Decimal("6000.00")),
                frequency="annual",
            )
        ],
        verified_at=date(2026, 6, 1),
    )


def test_scheme_to_text_includes_key_fields() -> None:
    text = scheme_to_text(_scheme())
    for fragment in ("PM-KISAN", "farmers", "6000", "pmkisan.gov.in", "200000"):
        assert fragment in text


def test_scheme_to_text_covers_all_fields() -> None:
    from bharatai.domain.enums import Category, DocumentType, Gender, IndianState, ResidenceType
    from bharatai.domain.value_objects import DateRange

    scheme = Scheme(
        name="Full",
        code="F1",
        department="Dept",
        level="central",
        state=IndianState.RAJASTHAN,
        category_tags=["agri"],
        description="A description.",
        eligibility_criteria=EligibilityCriteria(
            min_age=18,
            max_age=60,
            allowed_genders=[Gender.FEMALE],
            allowed_categories=[Category.SC],
            max_annual_income=Money(amount=Decimal("200000")),
            allowed_states=[IndianState.RAJASTHAN],
            residence_types=[ResidenceType.RURAL],
            requires_bpl=True,
            min_disability_percentage=40,
            required_documents=[DocumentType.AADHAAR],
            raw_rules_text="extra rules",
            custom_flags={"widow": "yes"},
        ),
        benefits=[
            SchemeBenefit(
                description="benefit", amount=Money(amount=Decimal("6000")), frequency="annual"
            )
        ],
        application_window=DateRange(start=date(2026, 1, 1), end=date(2026, 12, 31)),
        source_url="https://example.gov.in",
        verified_at=date(2026, 6, 1),
    )
    text = scheme_to_text(scheme)
    for fragment in (
        "Full", "F1", "Dept", "central", "RJ", "agri", "description",
        "minimum age 18", "maximum age 60", "female", "SC", "200000",
        "rural", "below poverty line", "disability 40", "aadhaar",
        "widow=yes", "extra rules", "benefit", "6000", "2026-12-31",
        "example.gov.in", "2026-06-01",
    ):
        assert fragment in text


def test_split_text_windows_with_overlap() -> None:
    pieces = split_text("abcdefghij" * 10, chunk_size=40, overlap=10)
    assert len(pieces) > 1
    assert all(len(piece) <= 40 for piece in pieces)


def test_split_text_short_and_empty() -> None:
    assert split_text("short", 100, 10) == ["short"]
    assert split_text("   ", 100, 10) == []


def test_split_text_rejects_bad_overlap() -> None:
    with pytest.raises(ValueError, match="overlap"):
        split_text("text", chunk_size=10, overlap=10)


def test_build_chunks_carries_provenance() -> None:
    chunks = build_chunks([_scheme()])
    assert chunks
    assert all(c.source_title == "PM-KISAN" for c in chunks)
    assert all(c.source_url == "https://pmkisan.gov.in" for c in chunks)
    assert all(c.score == 0.0 for c in chunks)


def test_scheme_to_text_includes_extended_eligibility_fields() -> None:
    scheme = Scheme(
        name="Widow Pension",
        eligibility_criteria=EligibilityCriteria(
            allowed_genders=[Gender.FEMALE, Gender.TRANSGENDER],
            residence_types=[ResidenceType.RURAL],
            min_disability_percentage=40,
            custom_flags={"widow": "yes"},
        ),
    )
    text = scheme_to_text(scheme).lower()
    for fragment in ("female", "transgender", "rural", "disability 40", "widow=yes"):
        assert fragment in text


def test_build_chunks_skips_inactive_schemes() -> None:
    active = _scheme()
    inactive = Scheme(name="Discontinued", description="Old scheme.", is_active=False)
    chunks = build_chunks([active, inactive])
    assert chunks
    assert {c.source_title for c in chunks} == {"PM-KISAN"}
