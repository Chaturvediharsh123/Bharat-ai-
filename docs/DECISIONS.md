# Design Decisions (v1)

The locked product decisions for v1, and why. These shape what the system does and does not do.

## 1. Local-first deployment

**Decision:** Everything runs on one machine (Streamlit + Ollama + PaddleOCR + SQLite); no auth,
single-operator. Built behind `LLMPort`/`OcrPort` so a remote/cloud mode is a later config swap.

**Why:** Streamlit Community Cloud cannot run Ollama or PaddleOCR (~1 GB RAM, no GPU). The honest,
constraint-compliant (free/open-source) path is local/self-hosted — a citizen's machine or an
NGO/CSC operator kiosk. The "serves millions on free cloud + local Ollama" framing is mutually
exclusive and was dropped.

## 2. Hand-curated scheme corpus

**Decision:** A small set of high-impact schemes, each entered with `source_url` + `verified_at`.
No unsupervised bulk PDF scraping in v1. See [SCHEME_CURATION.md](SCHEME_CURATION.md).

**Why:** Every downstream verdict depends on scheme data being correct. Auto-scraped, authoritative-
looking criteria are too risky to ship unsupervised when a wrong rule can mislead a citizen.

## 3. Conservative / advisory outputs

**Decision:** All outputs are advisory, with a disclaimer and source links on every verdict. Never a
bare `NOT_ELIGIBLE` — a missing field yields `NEEDS_MORE_INFO` (with the missing fields and lower
confidence). Aadhaar is optional and its raw OCR text is never persisted. **No rupee "lost benefits"
figure** — recommendations are qualitative ("schemes you may have missed").

**Why:** A wrong eligibility verdict can make a genuinely-eligible poor citizen not apply (direct
harm); a precise rupee-loss number from unverified, self-asserted data is indefensible. The system
errs toward caution and verification.

## Engineering invariants (enforced)

- **Clean Architecture** with the inward dependency rule, checked by `import-linter` (7 contracts)
  and an AST domain-isolation test.
- **Deterministic eligibility core** — the LLM explains, never decides.
- **No-hallucination RAG** — min-score threshold → abstain → mandatory citations.
- **PII minimization** — `aadhaar_last4`/masked numbers only; free-text PII redacted; full IDs never
  stored (including in OCR `raw_text`).
- **Quality gate** — `ruff` + `mypy --strict` + `import-linter` + `pytest` at ≥95% coverage,
  runnable via `scripts/check.sh`.

## How this was built

Each phase (architecture → DB → knowledge → OCR → 7 agents → LangGraph → UI → testing →
optimization → docs) closed with an **adversarial multi-agent review** (find → independently verify →
fix → regression-test). Those reviews found and fixed real latent bugs in every implementation phase —
e.g. non-atomic migrations, lexicographic timestamp ordering, income misparsing, a path-traversal in
file reads, full-ID leakage in stored OCR text, and a reserved-`LogRecord`-key crash that silently
disabled reminders at the production log level.
