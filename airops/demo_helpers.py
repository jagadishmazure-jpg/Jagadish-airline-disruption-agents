"""Stdlib-only demo helpers (fully tested); demo/app.py is a thin wrapper."""

from __future__ import annotations

from . import crewlegality, rebooking
from .orchestrator import Orchestrator
from .telemetry import get_conn
from .views import run_query
from .weathersignal import FakeAtcSignal


def disruption_summary() -> dict:
    conn = get_conn()
    orch = Orchestrator(conn)
    by_cause = run_query(conn, "SELECT delay_code, COUNT(*) n FROM v_disrupted_flights GROUP BY delay_code")
    illegal = crewlegality.find_illegal_pairings(
        run_query(conn, "SELECT * FROM v_crew_status"))
    backlog = run_query(conn, "SELECT COUNT(*) n FROM v_rebooking_queue")
    return {
        "by_cause": by_cause,
        "illegal_pairings": len(illegal),
        "rebooking_backlog": backlog[0]["n"] if backlog else 0,
    }


def ask(question: str) -> dict:
    conn = get_conn()
    return Orchestrator(conn).ask(question)


def rebook_demo(pax_id: str = "PAX-M207-00") -> dict:
    conn = get_conn()
    row = conn.execute(
        "SELECT flight_no, final_dest, cabin FROM passengers WHERE pax_id = ?",
        (pax_id,)).fetchone()
    flight_no, dest, cabin = row
    origin = conn.execute(
        "SELECT origin FROM flights WHERE flight_no = ?", (flight_no,)).fetchone()[0]
    return {"pax_id": pax_id,
            "options": rebooking.rank_options(conn, origin, dest, cabin)}


def atc_demo(airport: str = "ORD") -> dict:
    return FakeAtcSignal().get(airport)
