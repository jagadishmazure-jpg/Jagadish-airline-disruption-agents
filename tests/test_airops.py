"""Regression checks for Jagadish-airline-disruption-agents (synthetic data)."""


import pytest

from airops import (
    audit,
    crewlegality,
    demo_helpers,
    escalation,
    feedback,
    orchestrator,
    pii,
    rebooking,
    sop_rag,
    telemetry,
    text2sql,
    views,
    weathersignal,
)


def fresh_conn():
    conn = telemetry.build_db()
    views.create_views(conn)
    return conn


# ---------- telemetry ----------

def test_seed_anchors_present():
    conn = fresh_conn()
    assert conn.execute("SELECT status FROM flights WHERE flight_no='MA-207'").fetchone()[0] == "cancelled"
    n = conn.execute("SELECT COUNT(*) FROM passengers WHERE flight_no='MA-207'").fetchone()[0]
    assert n == 42
    assert conn.execute("SELECT status FROM baggage WHERE tag_id='BAG-EXC-01'").fetchone()[0] == "mishandled"


def test_telemetry_deterministic():
    c1, c2 = telemetry.build_db(), telemetry.build_db()
    n1 = c1.execute("SELECT COUNT(*) FROM flights").fetchone()[0]
    n2 = c2.execute("SELECT COUNT(*) FROM flights").fetchone()[0]
    assert n1 == n2 > 20


def test_fictional_brand_only():
    conn = fresh_conn()
    names = " ".join(r[0] for r in conn.execute("SELECT flight_no FROM flights"))
    assert "MA-" in names
    for real in ("Delta", "United", "American", "Southwest", "Lufthansa"):
        assert real not in names


# ---------- gateway ----------

def test_select_only_blocks_writes():
    with pytest.raises(views.GatewayError):
        views.ensure_select_only("DELETE FROM flights")


def test_write_keyword_inside_string_literal_ok():
    q = views.ensure_select_only("SELECT * FROM flights WHERE status != 'deleted'")
    assert "LIMIT" in q


def test_non_select_rejected():
    with pytest.raises(views.GatewayError):
        views.ensure_select_only("DROP TABLE flights")


def test_limit_added_when_missing():
    assert views.ensure_select_only("SELECT 1").rstrip().endswith("LIMIT 100")


def test_run_query_returns_dicts():
    conn = fresh_conn()
    rows = views.run_query(conn, "SELECT flight_no FROM v_disrupted_flights")
    assert rows and isinstance(rows[0], dict)


# ---------- text2sql ----------

def test_detect_all_five_intents():
    assert text2sql.detect_intent("which flights are disrupted by cause?") == "disrupted_flights_by_cause"
    assert text2sql.detect_intent("any illegal crew pairings?") == "illegal_crew_pairings"
    assert text2sql.detect_intent("rebooking backlog size") == "rebooking_backlog"
    assert text2sql.detect_intent("baggage exceptions today") == "baggage_exceptions"
    assert text2sql.detect_intent("average delay by cause") == "delay_stats"


def test_detect_unknown_intent_none():
    assert text2sql.detect_intent("what is the meaning of life") is None


def test_answer_end_to_end():
    conn = fresh_conn()
    res = text2sql.answer(conn, "show disrupted flights by cause")
    assert res["intent"] == "disrupted_flights_by_cause"
    assert res["rows"] and not res["retried"]


def test_answer_unknown_question_escalates():
    conn = fresh_conn()
    with pytest.raises(text2sql.EscalationNeeded):
        text2sql.answer(conn, "tell me about quantum cryptography")


def test_self_correction_retry(monkeypatch):
    conn = fresh_conn()
    calls = {"n": 0}
    real = views.run_query

    def flaky(c, sql, params=()):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return real(c, sql, params)

    monkeypatch.setattr(text2sql, "run_query", flaky)
    res = text2sql.answer(conn, "rebooking backlog")
    assert res["retried"] is True and calls["n"] == 2


# ---------- crew legality (differentiator) ----------

def test_duty_limit_violation_cited():
    v = crewlegality.evaluate_crew({"duty_minutes": 930, "rest_hours": 12.0,
                                    "flight_minutes": 400, "consec_days": 3})
    assert [x.rule_id for x in v] == ["CL-DUTY-14"]


def test_rest_violation_cited():
    v = crewlegality.evaluate_crew({"duty_minutes": 300, "rest_hours": 8.0,
                                    "flight_minutes": 180, "consec_days": 2})
    assert [x.rule_id for x in v] == ["CL-REST-10"]


def test_flight_time_and_consec_violations():
    v = crewlegality.evaluate_crew({"duty_minutes": 600, "rest_hours": 12.0,
                                    "flight_minutes": 500, "consec_days": 7})
    assert [x.rule_id for x in v] == ["CL-FLIGHT-8", "CL-CONSEC-6"]


def test_legal_crew_no_violations():
    v = crewlegality.evaluate_crew({"duty_minutes": 400, "rest_hours": 12.0,
                                    "flight_minutes": 300, "consec_days": 3})
    assert v == []


def test_boundary_values_pass():
    v = crewlegality.evaluate_crew({"duty_minutes": 840, "rest_hours": 10.0,
                                    "flight_minutes": 480, "consec_days": 6})
    assert v == []


def test_find_illegal_pairings_finds_anchors():
    conn = fresh_conn()
    rows = views.run_query(conn, "SELECT * FROM v_crew_status")
    illegal = crewlegality.find_illegal_pairings(rows)
    ids = {p["crew_id"] for p in illegal}
    assert "C-ILLEGAL-01" in ids and "C-REST-02" in ids
    for p in illegal:
        assert p["violations"]  # exact rules cited


# ---------- rebooking (differentiator) ----------

def test_rank_options_best_first():
    conn = fresh_conn()
    ranked = rebooking.rank_options(conn, "ORD", "JFK", "Y")
    assert ranked[0]["rec_id"] == "REC-01"
    scores = [r["score"] for r in ranked]
    assert scores == sorted(scores)


def test_cabin_downgrade_penalized():
    conn = fresh_conn()
    ranked = rebooking.rank_options(conn, "ORD", "JFK", "J")
    rec2 = next(r for r in ranked if r["rec_id"] == "REC-02")
    assert rec2["cabin_mismatch"] == 1  # Y-only flight for a J passenger


def test_breakdown_present():
    conn = fresh_conn()
    top = rebooking.best_option(conn, "ORD", "JFK")
    assert "delay" in top["breakdown"] and "cabin" in top["breakdown"]


def test_no_options_returns_none():
    conn = fresh_conn()
    assert rebooking.best_option(conn, "XXX", "YYY") is None


# ---------- SOP RAG ----------

def test_rag_cites_crew_sop():
    rag = sop_rag.SopRag()
    hits = rag.retrieve("crew duty limit illegal pairing")
    assert hits and "sop-02-crew-legality.md" in hits[0]["citation"]


def test_rag_cites_rebooking_sop():
    rag = sop_rag.SopRag()
    hits = rag.retrieve("how should I rebook a misconnected passenger")
    assert any("sop-03" in h["citation"] for h in hits)


def test_rag_not_found_explicit():
    rag = sop_rag.SopRag()
    assert rag.answer("quantum cryptography policy") == sop_rag.NOT_FOUND


def test_rag_skips_title_only_intros():
    chunks = sop_rag.load_chunks()
    assert all(len(c["text"]) >= 20 for c in chunks)


# ---------- weather signal ----------

def test_fake_atc_ground_stop():
    sig = weathersignal.FakeAtcSignal().get("ORD")
    assert sig["ground_stop"] is True and sig["source"] == "fake"


def test_fake_atc_clear():
    assert weathersignal.FakeAtcSignal().get("JFK")["ground_stop"] is False


def test_live_gap_never_hallucinates():
    with pytest.raises(weathersignal.SignalGap):
        weathersignal.LiveAtcSignal().get("ORD")


def test_live_with_fetcher():
    live = weathersignal.LiveAtcSignal(fetcher=lambda a: {"airport": a, "ok": True})
    assert live.get("ORD")["ok"] is True


# ---------- escalation ----------

def test_tier_classification():
    assert escalation.tier_for({"kind": "cancellation"}) == "T4"
    assert escalation.tier_for({"kind": "rebooking"}) == "T3"
    assert escalation.tier_for({"kind": "info", "severity": "low"}) == "T1"


def test_cancellation_always_gated_and_approved():
    gate = escalation.ConfirmationGate(approver=lambda a: True)
    esc = escalation.Escalation(tier="T4", action={"name": "cancel_flight"})
    esc.run(gate)
    assert esc.gate_decision == "approved"


def test_gate_denied():
    gate = escalation.ConfirmationGate(approver=lambda a: False)
    esc = escalation.Escalation(tier="T3", action={"name": "reassign_crew"})
    esc.run(gate)
    assert esc.gate_decision == "denied"


def test_gate_timeout_without_approver():
    esc = escalation.Escalation(tier="T3", action={"name": "x"}).run(
        escalation.ConfirmationGate())
    assert esc.gate_decision == "timeout"


def test_t1_no_gate():
    esc = escalation.Escalation(tier="T1", action={"name": "notify"}).run(
        escalation.ConfirmationGate())
    assert esc.log == ["no-gate-needed"]


# ---------- audit ----------

def test_audit_chain_verifies():
    log = audit.AuditLog()
    log.record("ops", "open_case", {"flight": "MA-207"})
    log.record("ops", "rebook", {"pax": "PAX-M207-00"})
    ok, msg = log.verify_chain()
    assert ok and "2 entries verified" in msg


def test_audit_tamper_detected():
    log = audit.AuditLog()
    log.record("ops", "open_case", {})
    log.entries[0]["details"] = {"hacked": True}
    ok, msg = log.verify_chain()
    assert not ok


# ---------- pii + feedback ----------

def test_pii_scrub_email_phone_ssn():
    scrubbed, n = pii.scrub("mail me at jane@doe.com or 555-123-4567, ssn 123-45-6789")
    assert "[EMAIL]" in scrubbed and "[PHONE]" in scrubbed and "[SSN]" in scrubbed
    assert n == 3
    assert "jane@doe.com" not in scrubbed


def test_pii_scrub_clean_text_unchanged():
    scrubbed, n = pii.scrub("the flight was delayed")
    assert (scrubbed, n) == ("the flight was delayed", 0)


def test_feedback_stored_scrubbed():
    log = audit.AuditLog()
    e = feedback.capture_feedback(log, session_id="S1", turn_id="T1",
                                  rating="down",
                                  correction="call jane@doe.com about MA-207")
    assert e["details"]["correction"] == "call [EMAIL] about MA-207"
    assert e["details"]["pii_redactions"] == 1
    ok, _ = log.verify_chain()
    assert ok


def test_feedback_rejects_bad_rating():
    log = audit.AuditLog()
    with pytest.raises(feedback.FeedbackError):
        feedback.capture_feedback(log, session_id="S1", turn_id="T1", rating="meh")


def test_feedback_rejects_empty_correction_on_down():
    log = audit.AuditLog()
    with pytest.raises(feedback.FeedbackError):
        feedback.capture_feedback(log, session_id="S1", turn_id="T1",
                                  rating="down", correction="   ")


def test_feedback_rejects_blank_session():
    log = audit.AuditLog()
    with pytest.raises(feedback.FeedbackError):
        feedback.capture_feedback(log, session_id=" ", turn_id="T1", rating="up")


def test_list_feedback_filters_session():
    log = audit.AuditLog()
    feedback.capture_feedback(log, session_id="S1", turn_id="T1", rating="up")
    feedback.capture_feedback(log, session_id="S2", turn_id="T9", rating="up")
    assert len(feedback.list_feedback(log)) == 2
    assert len(feedback.list_feedback(log, session_id="S1")) == 1


# ---------- orchestrator ----------

def test_orchestrator_multi_intent_fanout():
    conn = fresh_conn()
    res = orchestrator.Orchestrator(conn).ask(
        "which flights are disrupted and are any crew pairings illegal?")
    assert "text2sql" in res["tools_used"] and "crew_legality" in res["tools_used"]


def test_orchestrator_crew_legality_cites_rule():
    conn = fresh_conn()
    res = orchestrator.Orchestrator(conn).ask("are any crew pairings illegal?")
    assert "CL-DUTY-14" in res["answer"]
    assert any("sop-02" in c for c in res["citations"])


def test_orchestrator_rebooking():
    conn = fresh_conn()
    res = orchestrator.Orchestrator(conn).ask("rebook PAX-M207-00")
    assert "rebooking" in res["tools_used"]
    assert "REC-01" in res["answer"]


def test_orchestrator_sop_rag():
    conn = fresh_conn()
    res = orchestrator.Orchestrator(conn).ask("what is the rebooking policy?")
    assert "sop_rag" in res["tools_used"]


def test_orchestrator_unmapped_escalates():
    conn = fresh_conn()
    res = orchestrator.Orchestrator(conn).ask("sing me a song")
    assert res["tools_used"] == []


# ---------- demo helpers ----------

def test_demo_summary_numbers():
    s = demo_helpers.disruption_summary()
    assert s["illegal_pairings"] >= 2
    assert s["rebooking_backlog"] > 0
    assert s["by_cause"]


def test_demo_ask_and_rebook():
    ans = demo_helpers.ask("disrupted flights")["answer"].lower()
    assert "disrupted_flights_by_cause" in ans
    r = demo_helpers.rebook_demo("PAX-M207-00")
    assert r["options"][0]["rec_id"] == "REC-01"


def test_demo_atc():
    assert demo_helpers.atc_demo("ORD")["ground_stop"] is True


# ---------- review fixes (grokbot-portfolio, 2026-10-18) ----------

def test_delay_projected_onto_duty_time():
    crew = {"crew_id": "C-X", "role": "fo", "assigned_flight": "MA-310",
            "duty_minutes": 700, "flight_minutes": 300, "rest_hours": 12.0, "consec_days": 2}
    assert crewlegality.find_illegal_pairings([crew]) == []
    hit = crewlegality.find_illegal_pairings([crew], {"MA-310": 165})
    assert hit and hit[0]["violations"][0][0] == "CL-DUTY-14"
    assert "projected duty_minutes=865" in hit[0]["violations"][0][2]


def test_already_illegal_crew_not_double_counted():
    crew = {"crew_id": "C-Y", "role": "captain", "assigned_flight": "MA-207",
            "duty_minutes": 930, "flight_minutes": 430, "rest_hours": 12.0, "consec_days": 3}
    hit = crewlegality.find_illegal_pairings([crew], {"MA-207": 60})
    assert [v[0] for v in hit[0]["violations"]] == ["CL-DUTY-14"]


def test_pii_keeps_dates_and_redacts_parenthesised_phone():
    from airops.pii import scrub
    out, n = scrub("MA-207 on 2026-10-18 was cancelled; call (555) 123-4567")
    assert "2026-10-18" in out and "[PHONE]" in out and "(" not in out.split("call")[1] and n == 1
