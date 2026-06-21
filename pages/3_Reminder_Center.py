"""Reminder Center — review deadline reminders for saved citizens."""
from __future__ import annotations

import streamlit as st

from ui_support import ADVISORY, services

st.title("⏰ Reminder Center")
st.warning(ADVISORY)

svc = services()
citizens = svc.citizens.list_all()
if not citizens:
    st.info("No citizens saved yet. Use the **Eligibility Assistant** to create one.")
    st.stop()

labels = {f"{c.full_name or 'Unnamed'} ({c.id[:8]})": c.id for c in citizens}
choice = st.selectbox("Citizen", list(labels))
reminders = svc.reminders.list_for(labels[choice])

if not reminders:
    st.caption("No reminders for this citizen yet.")
for reminder in reminders:
    due = reminder.due_date.isoformat() if reminder.due_date else "—"
    icon = {"due": "🔔", "expired": "⚠️", "scheduled": "🗓️"}.get(reminder.status.value, "•")
    st.write(f"{icon} **{reminder.title}** — due {due} · {reminder.status.value}")
    if reminder.description:
        st.caption(reminder.description)
