"""ReAct orchestrator with multi-intent fan-out.

Plan: detect one or more intents in the question (telemetry intents via
text2sql.detect_intent, SOP questions via the RAG, crew-legality checks,
rebooking requests). Act: run each matched tool. Observe: synthesize one
answer with citations. A question can fan out to several tools at once.
"""

from __future__ import annotations

import re
import sqlite3

from . import crewlegality, rebooking, sop_rag, text2sql
from .views import create_views, run_query


class Orchestrator:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        create_views(conn)
        self.rag = sop_rag.SopRag()

    def _telemetry_answers(self, question: str) -> list[dict]:
        intents = []
        for name, pattern, _ in text2sql.INTENT_PATTERNS:
            if pattern.search(question):
                intents.append(name)
        # de-dup while keeping order; "and" questions fan out naturally
        seen, uniq = set(), []
        for i in intents:
            if i not in seen:
                seen.add(i)
                uniq.append(i)
        out = []
        for intent in uniq:
            try:
                out.append(text2sql.answer(self.conn, intent))
            except text2sql.EscalationNeeded as exc:
                out.append({"intent": intent, "error": str(exc)})
        return out

    def _legality_answer(self) -> dict:
        rows = run_query(self.conn, "SELECT * FROM v_crew_status")
        delays = {r["flight_no"]: r["delay_minutes"] for r in run_query(
            self.conn, "SELECT flight_no, delay_minutes FROM v_disrupted_flights")}
        illegal = crewlegality.find_illegal_pairings(rows, delays)
        return {"illegal_pairings": illegal, "checked": len(rows)}

    def _rebook_answer(self, question: str) -> dict:
        m = re.search(r"rebook .*?(PAX[-\w]+)", question, re.I)
        pax_id = m.group(1).upper() if m else "PAX-M207-00"
        row = self.conn.execute(
            "SELECT flight_no, final_dest, cabin FROM passengers WHERE pax_id = ?",
            (pax_id,)).fetchone()
        if row is None:
            return {"error": f"unknown passenger {pax_id}"}
        flight_no, dest, cabin = row
        orig = self.conn.execute(
            "SELECT origin FROM flights WHERE flight_no = ?", (flight_no,)).fetchone()
        origin = orig[0] if orig else "ORD"
        return {"pax_id": pax_id, "options": rebooking.rank_options(
            self.conn, origin, dest, cabin)}

    def ask(self, question: str) -> dict:
        """Run the ReAct loop; return {answer, citations, tools_used}."""
        tools_used: list[str] = []
        parts: list[str] = []
        citations: list[str] = []

        tel = self._telemetry_answers(question)
        if tel:
            tools_used.append("text2sql")
            for t in tel:
                if "error" in t:
                    parts.append(f"[{t['intent']}] escalated: {t['error']}")
                else:
                    parts.append(f"[{t['intent']}] {len(t['rows'])} row(s): "
                                 + "; ".join(str(r) for r in t["rows"][:3]))

        if re.search(r"legal|illegal|duty|crew", question, re.I):
            tools_used.append("crew_legality")
            leg = self._legality_answer()
            parts.append(f"[crew_legality] {len(leg['illegal_pairings'])} illegal "
                         f"pairing(s) of {leg['checked']} crew checked")
            for p in leg["illegal_pairings"]:
                rules = ", ".join(v[0] for v in p["violations"])
                parts.append(f"  {p['crew_id']} ({p['role']}) on {p['assigned_flight']}: {rules}")
                citations.append("sop-02-crew-legality.md §Illegal pairing response")

        if re.search(r"rebook", question, re.I):
            tools_used.append("rebooking")
            rb = self._rebook_answer(question)
            if "error" in rb:
                parts.append(f"[rebooking] {rb['error']}")
            else:
                top = rb["options"][0] if rb["options"] else None
                if top:
                    parts.append(f"[rebooking] best for {rb['pax_id']}: {top['rec_id']} "
                                 f"(score {top['score']}: {top['breakdown']})")
                    citations.append("sop-03-rebooking-policy.md §Recovery options")

        if re.search(r"sop|policy|procedure|rule|how (do|should)", question, re.I):
            tools_used.append("sop_rag")
            rag_out = self.rag.answer(question)
            parts.append(f"[sop_rag] {rag_out}")
            for h in self.rag.retrieve(question):
                citations.append(h["citation"])

        if not tools_used:
            return {"answer": "I could not map that question to a tool; escalating.",
                    "citations": [], "tools_used": []}
        return {"answer": "\n".join(parts),
                "citations": sorted(set(citations)),
                "tools_used": tools_used}
