"""Settings — show the active configuration and the v1 posture."""
from __future__ import annotations

import streamlit as st

from ui_support import services

st.title("⚙️ Settings")

settings = services().settings

st.subheader("Deployment")
st.write(f"**Mode:** {settings.deployment_mode}")
st.write(f"**Environment:** {settings.app_env}")

st.subheader("Models (local, free / open-source)")
st.write(f"**LLM (Ollama):** {settings.llm.default_model} @ {settings.llm.base_url}")
st.write(f"**Embeddings:** {settings.embedding.model_name} ({settings.embedding.device})")
st.write(f"**OCR:** PaddleOCR (lang={settings.ocr.lang})")

st.subheader("Knowledge base")
st.write(f"**Index dir:** {settings.knowledge.index_dir}")
st.write(f"**Min similarity:** {settings.knowledge.min_score} · **top-k:** {settings.knowledge.top_k}")

st.subheader("Privacy & trust posture (v1)")
st.markdown(
    """
- Aadhaar/PAN are stored **masked only** — the full number is never persisted.
- All outputs are **advisory**; every result links to the official source.
- Eligibility is **deterministic**; the LLM only phrases explanations, never decides.
- No rupee "lost benefits" figure is shown — only qualitative suggestions.
- Runs **locally** (Streamlit + Ollama + PaddleOCR + SQLite); requires a local Ollama server.
"""
)
