# Performance & Optimization

Local LLM/OCR inference on CPU is the latency bottleneck. The design keeps the slow paths off the
critical path and caches deterministic work.

## What's implemented

- **LLM response cache** (`infrastructure/llm/caching.py`). `CachingLLM` wraps the `LLMPort` and
  memoizes **deterministic** completions (`temperature == 0`) by `sha256(system, prompt, max_tokens)`,
  LRU-bounded. Wired in the composition root, so repeated eligibility explanations and bureaucratic
  simplifications cost nothing the second time. Non-deterministic calls bypass the cache.
- **Persisted FAISS index.** The knowledge index is built once and persisted to
  `data/index/faiss` (`KnowledgeBasePort.rebuild`); retrieval reloads from disk rather than
  re-embedding the corpus each run.
- **Deterministic eligibility core.** Eligibility decisions are 100% rule-based and never touch the
  LLM — the LLM is invoked only to *phrase* an explanation, and only when a scheme has
  `raw_rules_text`. This keeps the most-used path instant.
- **Per-document content hash.** `DocumentRecord.checksum_sha256` is computed on upload, enabling
  duplicate detection (`DocumentRepository.find_by_checksum`) so identical files need not be
  re-OCR'd.
- **Fault isolation.** `@safe_node` in the graph means one slow/failing agent degrades that section
  rather than blocking the whole run.

## Tiered model selection

`Settings.llm` exposes three tiers; choose per task to trade latency for capability:

| Tier | Default | Use for |
|---|---|---|
| `fast_model` | `qwen2.5:7b` | profile normalization, plain-language simplification |
| `default_model` | `gemma3:12b` | scheme discovery, eligibility explanations |
| `heavy_model` | `qwen2.5:14b` | rare hard reasoning only |

All deterministic calls use `temperature=0.0` (also required for the cache to be sound).

## Recommended further work

- **Lazy/on-demand translation.** Generate the plain-language/translated text only when the citizen
  taps "explain" for a specific scheme, instead of translating every result at run end. The
  `BureaucracyTranslatorAgent` is already a standalone, idempotent string→string service, so the UI
  can call it on demand.
- **OCR-by-checksum skip.** Before re-running OCR, look up `find_by_checksum`; reuse the prior
  analysis for an identical upload.
- **Streaming UX.** The graph runner supports streaming super-steps — surface per-node progress so a
  long run never shows a frozen spinner.
- **Scale path.** SQLite (single writer) and in-process caches are right for local/kiosk use. For
  many concurrent citizens, swap the repository adapter for Postgres and move OCR/inference behind a
  worker queue — both are isolated behind ports.
