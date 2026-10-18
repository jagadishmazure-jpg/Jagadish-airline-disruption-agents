"""Thin Streamlit demo for the airline disruption agent.

Run:  pip install streamlit && streamlit run demo/app.py
All logic lives in airops/demo_helpers.py (stdlib, fully tested).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import streamlit as st
except ImportError:  # pragma: no cover
    raise SystemExit("pip install streamlit, then rerun: streamlit run demo/app.py")

from airops import demo_helpers  # noqa: E402

st.title("Meridian Air — Disruption Operations (demo)")
st.caption("Synthetic data. Nothing here is real airline operations data.")

with st.expander("Disruption summary"):
    st.json(demo_helpers.disruption_summary())

q = st.text_input("Ask about disruptions, crew legality, rebooking, or baggage",
                  "Which flights are disrupted and are any crew pairings illegal?")
if st.button("Ask"):
    st.json(demo_helpers.ask(q))

st.subheader("Rebook a passenger")
pax = st.text_input("Passenger ID", "PAX-M207-00")
if st.button("Find recovery options"):
    st.json(demo_helpers.rebook_demo(pax.strip() or "PAX-M207-00"))
