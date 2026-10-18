"""Intent -> SQL planner with a self-correction retry.

Five intents; on query failure the planner retries once with a simplified
query, then raises EscalationNeeded (never returns a fabricated answer).
"""

from __future__ import annotations

import re
import sqlite3

from .views import run_query


class EscalationNeeded(RuntimeError):
    """Raised when neither the planned nor the simplified query succeeds."""


INTENT_PATTERNS = [
    ("delay_stats",
     re.compile(r"average|avg|statistic|how (long|much)", re.I),
     "SELECT * FROM v_delay_stats ORDER BY avg_delay_min DESC"),
    ("disrupted_flights_by_cause",
     re.compile(r"disrupt|delayed|cancelled|cause|by (cause|reason)", re.I),
     "SELECT delay_code, COUNT(*) AS n FROM v_disrupted_flights "
     "GROUP BY delay_code ORDER BY n DESC"),
    ("illegal_crew_pairings",
     re.compile(r"crew|illegal|duty|pairing|legal", re.I),
     "SELECT crew_id, role, duty_minutes, rest_hours, consec_days, assigned_flight "
     "FROM v_crew_status"),
    ("rebooking_backlog",
     re.compile(r"rebook|backlog|misconnect|stranded|passenger", re.I),
     "SELECT status, COUNT(*) AS n FROM v_rebooking_queue GROUP BY status"),
    ("baggage_exceptions",
     re.compile(r"baggage|bag |luggage|mishandled|tracing", re.I),
     "SELECT status, COUNT(*) AS n FROM v_baggage_exceptions GROUP BY status"),
]

SIMPLIFIED = {
    "disrupted_flights_by_cause": "SELECT * FROM v_disrupted_flights",
    "illegal_crew_pairings": "SELECT crew_id, role FROM v_crew_status",
    "rebooking_backlog": "SELECT * FROM v_rebooking_queue",
    "baggage_exceptions": "SELECT * FROM v_baggage_exceptions",
    "delay_stats": "SELECT * FROM v_delay_stats",
}


def detect_intent(question: str) -> str | None:
    for name, pattern, _ in INTENT_PATTERNS:
        if pattern.search(question):
            return name
    return None


def plan_sql(intent: str) -> str:
    for name, _, sql in INTENT_PATTERNS:
        if name == intent:
            return sql
    raise EscalationNeeded(f"no plan for intent {intent!r}")


def answer(conn: sqlite3.Connection, question: str) -> dict:
    """Answer a question; returns {intent, sql, rows, retried}."""
    intent = detect_intent(question)
    if intent is None:
        raise EscalationNeeded("no intent matched; escalating")
    try:
        rows = run_query(conn, plan_sql(intent))
        return {"intent": intent, "sql": plan_sql(intent), "rows": rows, "retried": False}
    except Exception:
        try:  # one self-correction retry with a simplified query
            rows = run_query(conn, SIMPLIFIED[intent])
            return {"intent": intent, "sql": SIMPLIFIED[intent],
                    "rows": rows, "retried": True}
        except Exception as exc:
            raise EscalationNeeded(f"query failed after retry: {exc}") from exc
