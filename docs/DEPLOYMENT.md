# BharatAI — Deployment & Run Guide

BharatAI is **local-first**: the app, the LLM (Ollama), OCR (PaddleOCR), embeddings, and the
database all run on one machine. This is the supported v1 deployment (see
[DECISIONS.md](DECISIONS.md) for why).

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) running locally, with the models pulled:
  ```bash
  ollama pull gemma3:12b      # default (discovery / eligibility explanations)
  ollama pull qwen2.5:7b      # fast (profile / translation)
  ollama pull qwen2.5:14b     # heavy (hard reasoning, optional)
  ```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # adjust paths/models if needed
```

The heavy ML libraries (faiss-cpu, llama-index, sentence-transformers, torch, paddleocr,
paddlepaddle) are declared in `pyproject.toml`. On first use, sentence-transformers downloads the
embedding model (~130 MB) and PaddleOCR downloads its detection/recognition models.

> **Known platform note (PaddleOCR/CPU):** some `paddlepaddle` CPU builds crash in the oneDNN
> kernel. The adapter defaults to `enable_mkldnn=False` to avoid this; leave it off on CPU.

## Run

```bash
streamlit run streamlit_app.py
```

`streamlit_app.py` + `ui_support.py` build the composition root (`bharatai.bootstrap.build_container`)
once and hand the `ServiceBundle` to the pages under `pages/`. No business logic lives in the UI.

## Configuration (`.env`)

Settings are typed (`bharatai.config.AppSettings`) and read with the `__` nested delimiter:

| Variable | Default | Meaning |
|---|---|---|
| `LLM__DEFAULT_MODEL` | `gemma3:12b` | discovery/eligibility model |
| `LLM__BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `EMBEDDING__MODEL_NAME` | `BAAI/bge-small-en-v1.5` | RAG embeddings |
| `KNOWLEDGE__MIN_SCORE` | `0.35` | retrieval abstain threshold |
| `DB__SQLITE_PATH` | `./data/bharatai.db` | database file |
| `OCR__UPLOAD_DIR` | `./data/uploads` | uploaded documents |

## Quality gate

```bash
bash scripts/check.sh        # ruff + mypy --strict + import-linter + pytest + coverage(≥95%)
pytest -m slow               # real-model tests (bge embeddings, PaddleOCR) — downloads models
```

## Why not Streamlit Community Cloud?

Streamlit Community Cloud (~1 GB RAM, no GPU, no co-located model server) **cannot** run Ollama or
PaddleOCR. The codebase is built behind `LLMPort`/`OcrPort`, so a future remote-inference deployment
is a config swap — but the **supported v1 path is local/self-hosted** (a citizen's machine, or an
NGO/CSC operator kiosk). Do not deploy the UI to a host that lacks the local model servers.

## Data & privacy

`data/` (the SQLite DB, FAISS index, uploads) is gitignored and lives on the local machine. Full
Aadhaar/PAN numbers are never persisted — only masked forms; free-text fields are PII-redacted. On
ephemeral/cloud filesystems this data is lost on restart, which is another reason v1 is local-first.
