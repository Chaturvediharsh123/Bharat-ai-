"""Eligibility Assistant — run the full BharatAI agent pipeline for a citizen."""
from __future__ import annotations

from datetime import date

import plotly.graph_objects as go
import streamlit as st

from bharatai.common.ids import new_id, now_utc
from bharatai.orchestration.state import BharatState
from ui_support import ADVISORY, STATUS_BADGE, services

st.title("✅ Eligibility Assistant")
st.warning(ADVISORY)

svc = services()
schemes = svc.schemes.list_active()
if not schemes:
    st.info("No schemes indexed yet — open **Government Schemes** and load the demo corpus first.")
    st.stop()

with st.form("citizen"):
    name = st.text_input("Full name")
    c1, c2, c3 = st.columns(3)
    dob = c1.date_input("Date of birth", value=date(1990, 1, 1), min_value=date(1920, 1, 1))
    gender = c2.selectbox("Gender", ["", "female", "male", "transgender", "other"])
    category = c3.selectbox("Category", ["", "GEN", "OBC", "SC", "ST", "EWS"])
    c4, c5, c6 = st.columns(3)
    income = c4.number_input("Annual income (Rs)", min_value=0, value=150000, step=5000)
    state = c5.text_input("State (name or code, e.g. Rajasthan / RJ)")
    bpl = c6.checkbox("Below poverty line")
    language = st.selectbox("Explain in language", ["en", "hi", "ta", "bn", "te"])
    submitted = st.form_submit_button("Check my eligibility")

if not submitted:
    st.stop()

raw = {
    "name": name,
    "dob": dob.isoformat(),
    "gender": gender or None,
    "category": category or None,
    "income": income,
    "state": state or None,
    "is_bpl": bpl,
}
raw = {key: value for key, value in raw.items() if value not in (None, "")}

state_obj = BharatState(
    run_id=new_id(),
    now=now_utc(),
    raw_input=raw,
    candidate_schemes=schemes,
    target_language=language,
)
with st.spinner("Running the BharatAI agents (profile → discovery → eligibility → ...)"):
    out = svc.graph_runner.run(state_obj)

# Persist the results (citizen first to satisfy foreign keys).
if out.citizen_profile is not None:
    svc.citizens.save(out.citizen_profile)
if out.eligibility_results:
    svc.eligibility.save_results(out.eligibility_results)
if out.reminders:
    svc.reminders.save_plan(out.reminders, [])

scheme_name = {s.id: s.name for s in out.discovered_schemes}

st.subheader("Eligibility")
if out.eligibility_results:
    fig = go.Figure(
        go.Bar(
            x=[scheme_name.get(r.scheme_id, r.scheme_id) for r in out.eligibility_results],
            y=[round(r.score * 100) for r in out.eligibility_results],
            marker_color=[
                {"eligible": "#2e7d32", "not_eligible": "#c62828", "needs_more_info": "#f9a825"}.get(
                    r.status.value, "#9e9e9e"
                )
                for r in out.eligibility_results
            ],
        )
    )
    fig.update_layout(yaxis_title="Criteria met (%)", height=320, margin=dict(t=10))
    st.plotly_chart(fig, use_container_width=True)

for result in out.eligibility_results:
    name_ = scheme_name.get(result.scheme_id, result.scheme_id)
    badge = STATUS_BADGE.get(result.status.value, result.status.value)
    with st.expander(f"{badge} — {name_}  ·  confidence {result.confidence:.0%}"):
        st.write(result.explanation or "")
        for ev in result.evaluations:
            mark = "✅" if ev.passed else "❌"
            st.caption(f"{mark} {ev.criterion}: expected {ev.expected}, you have {ev.actual}")
        if result.missing_profile_fields:
            st.info("Add to confirm: " + ", ".join(result.missing_profile_fields))

if out.recommendations:
    st.subheader("💡 Schemes you may be missing")
    for rec in out.recommendations:
        st.write(f"**{rec.scheme_name}** — {rec.reason}")

if out.reminders:
    st.subheader("⏰ Reminders")
    for reminder in out.reminders:
        due = reminder.due_date.isoformat() if reminder.due_date else "—"
        st.write(f"{reminder.title} — due {due} ({reminder.status.value})")

for translation in out.translations:
    st.subheader(f"🌐 Plain-language summary ({translation.target_language})")
    st.write(translation.simplified_text)
    for warning in translation.warnings:
        st.caption("⚠️ " + warning)

if out.errors:
    st.error(
        "Some steps had issues (results still shown where possible): "
        + "; ".join(f"{e.node}: {e.message}" for e in out.errors)
    )
