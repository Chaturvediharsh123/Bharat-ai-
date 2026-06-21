"""Shared helpers for the BharatAI Streamlit app (lives outside the bharatai package).

The Streamlit delivery app is the composition/entry layer: it wires the bharatai library
together. Keeping it outside the package keeps the library's dependency contracts clean.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from bharatai.bootstrap import get_container
from bharatai.bootstrap.service_bundle import ServiceBundle
from bharatai.domain.enums import Category, DocumentType, IndianState
from bharatai.domain.scheme import EligibilityCriteria, Scheme, SchemeBenefit
from bharatai.domain.value_objects import DateRange, Money

ADVISORY = (
    "⚠️ BharatAI is advisory only — it is **not** an official government decision. "
    "Always verify eligibility and deadlines on the official scheme portal."
)

STATUS_BADGE = {
    "eligible": "✅ Eligible",
    "not_eligible": "❌ Not eligible",
    "needs_more_info": "ℹ️ Needs more info",
    "pending": "⏳ Pending",
}


def services() -> ServiceBundle:
    """Return the process-wide wired services (built once via the composition root)."""
    return get_container().services


def demo_schemes() -> list[Scheme]:
    """A small, hand-curated set of high-impact schemes (with provenance) for the demo."""
    return [
        Scheme(
            name="PM-KISAN",
            code="PM-KISAN",
            description="Income support of Rs 6000 per year to small and marginal farmer families.",
            department="Ministry of Agriculture",
            level="central",
            category_tags=["agriculture", "income support"],
            eligibility_criteria=EligibilityCriteria(
                max_annual_income=Money(amount=Decimal("200000")),
                required_documents=[DocumentType.AADHAAR, DocumentType.INCOME],
                raw_rules_text="Small and marginal farmer families owning cultivable land.",
            ),
            benefits=[
                SchemeBenefit(
                    description="Rs 6000 per year in three installments",
                    amount=Money(amount=Decimal("6000")),
                    frequency="annual",
                )
            ],
            application_window=DateRange(end=date(2026, 12, 31)),
            source_url="https://pmkisan.gov.in",
            verified_at=date(2026, 6, 1),
        ),
        Scheme(
            name="Pradhan Mantri Awas Yojana (PMAY)",
            code="PMAY",
            description="Subsidy to help economically weaker families build or buy a pucca house.",
            department="Ministry of Housing and Urban Affairs",
            level="central",
            category_tags=["housing"],
            eligibility_criteria=EligibilityCriteria(
                max_annual_income=Money(amount=Decimal("300000")),
                required_documents=[DocumentType.AADHAAR, DocumentType.INCOME, DocumentType.DOMICILE],
                raw_rules_text="Economically weaker section / low-income households without a pucca house.",
            ),
            benefits=[
                SchemeBenefit(description="Interest subsidy on home loan", frequency="one-time")
            ],
            application_window=DateRange(end=date(2026, 9, 30)),
            source_url="https://pmaymis.gov.in",
            verified_at=date(2026, 6, 1),
        ),
        Scheme(
            name="Post-Matric Scholarship (SC/ST)",
            code="PMS-SCST",
            description="Scholarship covering tuition and maintenance for SC/ST students after class 10.",
            department="Ministry of Social Justice",
            level="central",
            category_tags=["education", "scholarship"],
            eligibility_criteria=EligibilityCriteria(
                allowed_categories=[Category.SC, Category.ST],
                max_annual_income=Money(amount=Decimal("250000")),
                required_documents=[DocumentType.AADHAAR, DocumentType.INCOME, DocumentType.BONAFIDE],
                raw_rules_text="SC/ST students enrolled in a recognised post-matriculation course.",
            ),
            benefits=[SchemeBenefit(description="Tuition + maintenance allowance", frequency="annual")],
            application_window=DateRange(end=date(2026, 10, 31)),
            source_url="https://scholarships.gov.in",
            verified_at=date(2026, 6, 1),
        ),
        Scheme(
            name="National Old Age Pension (NSAP)",
            code="NSAP-OAP",
            description="Monthly pension for elderly citizens below the poverty line.",
            department="Ministry of Rural Development",
            level="central",
            category_tags=["pension", "elderly"],
            eligibility_criteria=EligibilityCriteria(
                min_age=60,
                requires_bpl=True,
                required_documents=[DocumentType.AADHAAR],
                allowed_states=[IndianState.RAJASTHAN, IndianState.UTTAR_PRADESH, IndianState.BIHAR],
                raw_rules_text="Citizens aged 60+ belonging to a below-poverty-line household.",
            ),
            benefits=[
                SchemeBenefit(
                    description="Monthly old-age pension",
                    amount=Money(amount=Decimal("1000")),
                    frequency="monthly",
                )
            ],
            source_url="https://nsap.nic.in",
            verified_at=date(2026, 6, 1),
        ),
    ]
