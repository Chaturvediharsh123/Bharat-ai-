"""Government Schemes page — load the demo corpus and browse indexed schemes."""
from __future__ import annotations

import streamlit as st

from ui_support import ADVISORY, demo_schemes, services

st.title("🏛️ Government Schemes")
st.warning(ADVISORY)

svc = services()

if st.button("Load demo scheme corpus (builds the search index)"):
    with st.spinner("Indexing schemes (first run downloads the embedding model)..."):
        count = svc.schemes.seed(demo_schemes())
    st.success(f"Indexed {count} active schemes.")

schemes = svc.schemes.list_active()
st.caption(f"{len(schemes)} active scheme(s) indexed.")

for scheme in schemes:
    with st.expander(scheme.name):
        st.write(scheme.description)
        criteria = scheme.eligibility_criteria
        if criteria.max_annual_income is not None:
            st.write(f"**Income limit:** up to Rs {criteria.max_annual_income.amount}")
        if criteria.allowed_categories:
            st.write("**Categories:** " + ", ".join(c.value for c in criteria.allowed_categories))
        if criteria.required_documents:
            st.write("**Documents:** " + ", ".join(d.value for d in criteria.required_documents))
        for benefit in scheme.benefits:
            st.write(f"**Benefit:** {benefit.description}")
        if scheme.application_window and scheme.application_window.end:
            st.write(f"**Apply by:** {scheme.application_window.end.isoformat()}")
        if scheme.source_url:
            st.markdown(f"[Official source]({scheme.source_url})")
        if scheme.verified_at:
            st.caption(f"Last verified: {scheme.verified_at.isoformat()}")
