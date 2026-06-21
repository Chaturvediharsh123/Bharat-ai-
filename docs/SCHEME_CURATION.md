# Scheme Curation Guide

The v1 knowledge corpus is **small and hand-curated** (not bulk-scraped). Every scheme must carry
provenance, because every eligibility verdict, recommendation, and reminder downstream depends on
the scheme data being correct. Start with a few high-impact schemes done correctly (PM-KISAN, PMAY,
NSAP pensions, post-matric scholarships) rather than many done unreliably.

## Anatomy of a `Scheme`

A scheme is a `bharatai.domain.Scheme`. The eligibility engine reads the **structured**
`EligibilityCriteria`; free-form rules go in `raw_rules_text` (used only to *phrase* an explanation,
never to decide).

```python
from datetime import date
from decimal import Decimal
from bharatai.domain.scheme import Scheme, EligibilityCriteria, SchemeBenefit
from bharatai.domain.value_objects import DateRange, Money
from bharatai.domain.enums import Category, DocumentType, IndianState

pm_kisan = Scheme(
    name="PM-KISAN",
    code="PM-KISAN",                       # unique → enables upsert-by-code on re-ingest
    department="Ministry of Agriculture",
    level="central",                        # "central" | "state"
    state=None,                             # None = all-India; else an IndianState
    description="Income support for small and marginal farmer families.",
    category_tags=["agriculture", "income-support"],
    eligibility_criteria=EligibilityCriteria(
        max_annual_income=Money(amount=Decimal("200000")),
        required_documents=[DocumentType.AADHAAR],
        # also available: min_age/max_age, allowed_genders, allowed_categories,
        # allowed_states, residence_types, requires_bpl, min_disability_percentage,
        # raw_rules_text, custom_flags
    ),
    benefits=[SchemeBenefit(description="Rs 6000 per year", amount=Money(amount=Decimal("6000")),
                            frequency="annual")],
    application_window=DateRange(start=date(2025, 1, 1), end=date(2025, 12, 31)),
    source_url="https://pmkisan.gov.in",    # REQUIRED — shown next to every verdict
    verified_at=date(2026, 6, 1),           # REQUIRED — "last verified" date
    is_active=True,                          # inactive schemes are never indexed/recommended
)
```

## Rules

1. **Provenance is mandatory.** Every scheme needs `source_url` and `verified_at`. The UI shows
   these next to every eligibility verdict so the citizen can verify.
2. **Structure what you can.** Each `EligibilityCriteria` field you fill becomes a deterministic,
   explainable check. Anything left in `raw_rules_text` only produces an LLM-phrased note.
3. **Deadlines drive reminders.** Only set `application_window.end` when you have verified it — the
   Reminder agent builds deadline reminders from it.
4. **Mark discontinued schemes `is_active=False`** — they are excluded from indexing and
   recommendations so a stale scheme can never be cited.

## Ingesting

Persist + index via the service (used by the UI / a seed script):

```python
container.services.schemes.seed([pm_kisan, ...])   # upserts by code AND rebuilds the FAISS index
```

`seed()` calls `SchemeRepository.upsert_by_code` (so re-running updates in place) and then
`KnowledgeBasePort.rebuild(active_schemes)` to refresh retrieval. Because the corpus is small,
a full rebuild on change is the norm in v1.

## Validating your corpus

After editing schemes, run the gate (`bash scripts/check.sh`) and sanity-check retrieval:

```python
container.services.knowledge.answer("financial help for farmers")  # should cite PM-KISAN
container.services.knowledge.answer("zzz nonsense")                 # should abstain (NO_ANSWER)
```
