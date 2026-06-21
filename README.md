# 🇮🇳 BharatAI — Autonomous Citizen Intelligence System

An **agentic AI bureaucracy copilot** that helps Indian citizens discover government
schemes, check eligibility, validate documents, simplify bureaucratic language, spot
missed benefits, and stay on top of deadlines — running entirely on **free, open-source,
local** infrastructure.

> ⚠️ **Advisory only.** BharatAI provides guidance, not official government decisions.
> Always verify on the official scheme portal. Eligibility is computed from the
> information you provide against a curated knowledge base that may be incomplete.

## Status
**Complete.** All 16 phases delivered: domain → database → knowledge base → OCR → 7 agents →
LangGraph orchestration → Streamlit UI → testing → optimization → docs. **183 tests, ≥95% coverage**,
`mypy --strict` clean, and 7 architecture contracts enforced. Each phase closed with an adversarial
multi-agent review that found and fixed real latent bugs.

## Documentation
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — layers, the 7 agents, RAG, orchestration, data flow
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — local-first runbook (Ollama, models, run, config)
- [docs/SCHEME_CURATION.md](docs/SCHEME_CURATION.md) — how to add government schemes
- [docs/OPTIMIZATION.md](docs/OPTIMIZATION.md) — caching, tiered models, latency
- [docs/DECISIONS.md](docs/DECISIONS.md) — the locked v1 product decisions and why

## Tech stack (100% free / open-source)
Streamlit · Plotly · Python 3.11+ · LangGraph · Ollama (qwen2.5:14b/7b, gemma3:12b) ·
LlamaIndex + FAISS · sentence-transformers (bge-small-en-v1.5) · PaddleOCR · SQLite ·
pydantic v2 · python-dotenv · pytest.

## Architecture
Clean Architecture (Ports & Adapters) with a strict **inward dependency rule**:

```
ui  →  orchestration  →  agents  →  application  →  domain
                  infrastructure  ──implements──▶  application.ports
                  bootstrap  ──(composition root: wires every layer)
```

Enforced in CI by `import-linter` (see `[tool.importlinter]` in `pyproject.toml`):
domain depends on nothing, agents never import infrastructure, UI never imports AI/DB internals.

## Project layout
```
bharatai/
  domain/          # locked entities, value objects, enums (depends on nothing)
  application/     # ports (Protocols) + services + use-cases
  infrastructure/  # SQLite, Ollama, PaddleOCR, LlamaIndex+FAISS adapters
  agents/          # the 7 reasoning agents
  orchestration/   # LangGraph state, nodes, routers, runner
  ui/              # Streamlit pages + components
  bootstrap/       # dependency-injection composition root
  config/  common/ # settings, logging, exceptions, PII redaction
tests/             # unit · architecture (import contracts) · integration · fakes
```

## v1 product decisions
- **Local-first demo** — Streamlit + Ollama + PaddleOCR + SQLite on one machine.
- **Hand-curated scheme corpus** — high-impact schemes with source links + verified dates.
- **Conservative / advisory** — disclaimers, source links, Aadhaar optional and its raw
  OCR text never persisted, and **no rupee "lost benefits" figure** (qualitative only).

## Getting started
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
ollama pull gemma3:12b && ollama pull qwen2.5:7b   # local LLM
streamlit run streamlit_app.py
```
Full setup + configuration is in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Quality gate
```bash
bash scripts/check.sh        # ruff + mypy --strict + import-linter + pytest + coverage (≥95%)
pytest -m slow               # optional: real-model tests (bge embeddings, PaddleOCR)
```

## Roadmap (all delivered)
1 Architecture · 2 Folder structure · 3 Database · 4 Knowledge base · 5 OCR · 6 Profile agent ·
7 Eligibility · 8 Document · 9 Translator · 10 Recommendation · 11 Reminder · 12 LangGraph ·
13 Streamlit · 14 Testing · 15 Optimization · 16 Docs — ✅
