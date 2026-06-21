# BharatAI — Architecture

BharatAI is built on **Clean Architecture (Ports & Adapters)** with a strict, machine-enforced
inward dependency rule. Every "never mix X with Y" rule is a compile/lint-time invariant, not a
guideline.

## Layers & the dependency rule

```
  ui/            Streamlit pages + components          imports → application services + domain ONLY
  orchestration/ LangGraph: state, nodes, routers      imports → agents + ports
  agents/        the 7 reasoning agents                imports → ports + domain  (NEVER db/ocr/llm libs)
  infrastructure/ SQLite, Ollama, PaddleOCR, FAISS     implements → ports
  application/   ports (Protocols) + services + use-cases   imports → domain ONLY
  domain/        entities, value objects, enums        imports → NOTHING (stdlib + pydantic)
  config/  common/   typed settings; logging, exceptions, PII redaction   (cross-cutting)
  bootstrap/     composition root                      the ONLY module that imports every layer
```

Dependencies point **inward**. Enforced in CI by `import-linter` (`[tool.importlinter]` in
`pyproject.toml`) with 7 contracts: domain depends on nothing internal; application only on domain;
agents never import infrastructure; infrastructure only on application+domain; UI never imports
AI/DB internals. A unit test additionally AST-scans `domain/` for forbidden third-party imports.

## The domain contract

`bharatai.domain` is the single source of truth: pydantic v2 models with `extra="forbid"`,
self-generated UUID ids + UTC timestamps, **Money as `Decimal`** (stored as integer paise),
cross-entity links as string ids (so each entity maps 1:1 to a SQLite table). PII is minimized at
the contract level: profiles store `aadhaar_last4` only; document numbers are stored masked.

Entities: `CitizenProfile`, `Scheme` (+`EligibilityCriteria`, `SchemeBenefit`), `EligibilityResult`
(+`CriterionEvaluation`), `DocumentRecord` (embeds `OcrResult`), `Reminder`, `ApplicationHistoryEntry`.

## The seven agents (`bharatai.agents`)

| # | Agent | Responsibility |
|---|---|---|
| 1 | `CitizenProfileAgent` | normalize messy raw/OCR input → validated `CitizenProfile` (masks Aadhaar/PAN, redacts free-text PII) |
| 2 | `EligibilityIntelligenceAgent` | **deterministic** rule engine → `EligibilityResult`; LLM only *phrases* the explanation, never decides |
| 3 | `SchemeDiscoveryAgent` | RAG over the knowledge base → ranked schemes |
| 4 | `DocumentIntelligenceAgent` | OCR → extract → validate → score; returns `validated_doc_types` + readiness |
| 5 | `BureaucracyTranslatorAgent` | plain-language simplification/translation; preserves numbers, flags machine translation |
| 6 | `RecommendationAgent` | eligible-but-unavailed schemes (qualitative — **no rupee figure**) |
| 7 | `ReminderDeadlineAgent` | derive reminders from scheme windows + application state |

All agents share one contract — `BaseAgent[In, Out].run(data, ctx) -> Out` — and receive their
collaborators (LLM, knowledge, OCR, repositories) as injected **ports**, so each is unit-tested
fully offline with fakes.

## Knowledge base (RAG)

`bharatai.rag` (LlamaIndex node parsing + FAISS `IndexFlatIP` + local `bge-small-en-v1.5`
embeddings). Three-layer **no-hallucination guardrail**: a hard `min_score` threshold drops weak
retrievals before the LLM, an abstain path returns *"not available in the knowledge base"*, and every
answer carries source citations.

## Orchestration (LangGraph)

`bharatai.orchestration` wires the 7 agents into one compiled `StateGraph` over a typed
`BharatState` that embeds domain models. Each node is a thin agent wrapper; a `@safe_node`
decorator turns any agent failure into a recorded `NodeError` so the run degrades instead of
crashing. Conditional routers branch on intent / uploaded documents / requested scheme.

## Data flow

```
UI → build BharatState → GraphRunner.run()
  → Profile → Discovery (RAG) → [Document OCR if uploaded] → Eligibility (deterministic)
  → Recommendation → Reminder → Translator → Aggregate → services persist → UI renders (Plotly)
```

See [DECISIONS.md](DECISIONS.md) for the locked v1 product decisions and [DEPLOYMENT.md](DEPLOYMENT.md)
for the runbook.
