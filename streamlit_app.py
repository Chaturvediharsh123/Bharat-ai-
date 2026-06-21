"""BharatAI — Streamlit app entrypoint (run with: streamlit run streamlit_app.py).

This module is the composition/entry layer: it consumes the bharatai library via the
composition root. Multipage screens live in the sibling pages/ directory.
"""
from __future__ import annotations

import streamlit as st

from ui_support import ADVISORY, services

st.set_page_config(page_title="BharatAI", page_icon="🇮🇳", layout="wide")

st.title("🇮🇳 BharatAI — Autonomous Citizen Intelligence System")
st.caption("An agentic AI bureaucracy copilot that helps Indian citizens navigate government schemes.")
st.warning(ADVISORY)

svc = services()
active = svc.schemes.list_active()

left, right = st.columns(2)
left.metric("Schemes indexed", len(active))
right.metric("Deployment mode", svc.settings.deployment_mode)

st.markdown(
    """
### How it works
1. **Government Schemes** — load the demo scheme corpus (builds the search index).
2. **Eligibility Assistant** — enter your details; BharatAI's agents discover relevant schemes,
   check eligibility (deterministically), spot benefits you may be missing, and set reminders.
3. **Reminder Center** — review upcoming application deadlines.

Every result is **advisory** and links to the official source. Your Aadhaar/PAN are never stored
in full — only masked. Eligibility is computed from the information you provide.
"""
)

if not active:
    st.info("No schemes are indexed yet. Open **Government Schemes** and load the demo corpus to begin.")
