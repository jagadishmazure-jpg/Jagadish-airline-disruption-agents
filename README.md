# Jagadish-airline-disruption-agents

**Recruiter summary:** Airline disruptions cascade fast — one cancelled flight strands 42 passengers, ticks crew duty clocks toward illegality, and loses bags. This repo is an end-to-end disruption-operations agent: it answers open-ended ops questions over synthetic telemetry, enforces crew-legality rules with cited violations, ranks rebooking options with transparent scoring, and stops every safety-critical action at a human confirmation gate. Proof: 82 regression checks green; the demo finds 12 disrupted flights, 2 illegal crew pairings, and a 42-passenger rebooking backlog in one query.

## Problem → approach → outcome

**Problem.** Disruption desks juggle three questions at once — what broke, who is affected, what recovery is legal — under time pressure, where a wrong crew assignment grounds a flight.

**Approach.** A ReAct orchestrator fans out across five tools (text-to-SQL over read-only views, SOP RAG, crew-legality engine, rebooking optimizer, ATC/weather signal), classifies every event into T1–T4 escalation tiers, and gates T3/T4 actions on human confirmation. Every step lands in a hash-chained audit log.

**Outcome.** Deterministic, testable operations intelligence: ask "which flights are disrupted and are any crew pairings illegal?" and get cause-grouped counts plus the exact rules violated, with SOP citations.

## How it works

1. `airops/telemetry.py` builds a seeded SQLite world (fictional Meridian Air): flights, crew with duty clocks, passengers, baggage, recovery schedule.
2. `airops/text2sql.py` maps questions to 5 intents → fixed SELECT templates → `views.py` gateway (SEC-SELECT-01/02/03, plus 04: views only, via a SQLite authorizer) → one self-correction retry, then explicit escalation.
3. `airops/crewlegality.py` evaluates every crew record against CL-DUTY-14 / CL-REST-10 / CL-FLIGHT-8 / CL-CONSEC-6 (simplified illustrative rules, not FAR 117), citing each violation, and projects each disrupted flight's delay onto its assigned crew's duty time.
4. `airops/rebooking.py` ranks recovery itineraries: `1.0*delay + 4.0*cabin + 6.0*conn-risk`, with the arithmetic shown.
5. `airops/sop_rag.py` retrieves SOP sections with `file §section` citations; says so when nothing matches.
6. `airops/escalation.py` tiers events; cancellations and duty-limit crew moves always need confirmation.
7. `airops/audit.py` + `airops/feedback.py` record everything tamper-evidently; feedback text is PII-scrubbed first.

Real run (seed 42):

```
>>> from airops import demo_helpers
>>> demo_helpers.disruption_summary()
{'by_cause': [{'delay_code': 'ATC', 'n': 2}, {'delay_code': 'CREW', 'n': 6},
              {'delay_code': 'MX', 'n': 1}, {'delay_code': 'WX', 'n': 3}],
 'illegal_pairings': 2, 'rebooking_backlog': 42}
>>> demo_helpers.rebook_demo('PAX-M207-00')['options'][0]
{'rec_id': 'REC-01', 'score': 3.3,
 'breakdown': '1.0*3.0h delay + 4.0*0 cabin + 6.0*0.05 conn-risk', ...}
```

(Re-checked by CI in the review section below.)

## How this differs from coldchain/retail

Same FDE spine (SQLite telemetry, text-to-SQL, SOP RAG, escalation, audit), but the domain machinery is airline-specific: a **crew-legality rules engine** (duty/rest/flight-time limits with cited violations, including the duty time a delay *will* add, which is meaningless outside aviation) and a **rebooking optimizer** (arrival-delay/cabin/connection-risk trade-offs). Cold-chain optimizes for temperature compliance; retail for demand signals; this repo optimizes for *legal recovery*.

## Guardrails and security controls

- SELECT-only SQL gateway with string-literal-aware write scanning (SEC-SELECT-01/02/03); views only, enforced by a SQLite authorizer (SEC-SELECT-04, ADR 0001); 100-row fetch cap
- T3/T4 confirmation gates; cancellations and duty-limit crew moves always gated; gate timeout denies
- Hash-chained audit with tamper detection (`verify_chain()`)
- PII scrubbing (email/phone/SSN → placeholders) before feedback storage
- Live ATC feed raises an explicit gap instead of hallucinating weather
- See `docs/threat-model.md` (STRIDE-lite)

## Limitations and known failures

- Crew-legality rules are simplified and illustrative — not FAR Part 117; do not use for real dispatch.
- The rebooking optimizer ranks a fixed synthetic recovery schedule, not live inventory.
- Intent detection is regex-based; genuinely novel phrasings escalate instead of answering.
- No LLM is wired in; the planner is deterministic (see interview-points for the production path).

## Standardization review (2026-10-18)

Reviewed against the portfolio standard after the build. Bugs found and fixed, each now pinned by a test:

1. **Crew legality ignored the disruption itself.** Rules were checked on current duty time only, so a first officer at 700 duty minutes assigned to MA-310 (165 min late) showed as legal, although operating it means 865 minutes, past the 14:00 (840) limit. `find_illegal_pairings` now projects each disrupted flight's delay onto its assigned crew and cites CL-DUTY-14 with the projected figure. It never double-counts a crew that is already over.
2. **PII scrubber redacted dates and missed `(555)` phones.** Its phone pattern matched any 10+ character digit run, so `2026-10-18` in a correction became `[PHONE]` (losing the date the correction was about), while `(555) 123-4567` left a stray `(`. It now uses the shared phone pattern.
3. **README "real run" output did not match the code.** The cause breakdown was shown sorted by count; the code returns it in `GROUP BY` order. The block below is generated by a real run and re-checked by CI.
4. **Gateway had no view allowlist.** It blocked writes but any base table or `sqlite_master` was readable through the planner path, and a caller-supplied `LIMIT 100000` skipped the 100-row cap. New rule `SEC-SELECT-04` is enforced by a SQLite authorizer (`authz.py`, ADR 0001), and rows past 100 are never fetched.

Differentiator on the seeded data (regenerated and checked by CI on every push):

<!-- run: python scripts/show_differentiator.py -->
```text
by cause: {'ATC': 2, 'CREW': 6, 'MX': 1, 'WX': 3}
illegal pairings: 2 | rebooking backlog: 42
now: []
with MA-310 165 min late: [('CL-DUTY-14', 'Duty period may not exceed 14:00 hours', 'projected duty_minutes=865 after a 165 min delay on MA-310 exceeds limit 840')]
best rebooking: REC-01 3.3 1.0*3.0h delay + 4.0*0 cabin + 6.0*0.05 conn-risk
```
<!-- /run -->

Test count (also checked by CI):

<!-- run: python scripts/count_tests.py -->
```text
82 tests collected
```
<!-- /run -->

### Authorizer template sync (2026-10-18)

The SQLite authorizer was updated to the shared strict, view-aware version.
A base-table read is allowed only when SQLite reports it on behalf of one of
the allowed views (the authorizer's view-name argument). A read with no view
name is denied. `sqlite_master` is always denied, even if listed, and so is
`load_extension`. The old version falsely denied a self-join of `v_crew_status`; a regression test covers it.
`tests/test_authorizer_sync.py` drives the authorizer directly, independent
of the text check. It covers comma joins and comment-obfuscated joins with a
base table, every view, and view self-joins.

Known residual: a read that uses no columns of a table behind a view is
allowed, because SQLite reports the unused side of a view self-join the same
way. So `SELECT count(*) FROM <that table>` or `EXISTS (SELECT 1 FROM ...)`
can still reveal a row count, but no column data. Any column reference is
denied.

## Built / Written-not-run / Planned

| Item | Status |
|---|---|
| Telemetry, 5 text-to-SQL intents, gateway | Built, 82 checks green |
| CI on every push: ruff, tests, docs drift check, hashed brand check, gitleaks; CodeQL; Dependabot | Built |
| Crew-legality engine (4 rules) | Built, tested incl. boundary values |
| Rebooking optimizer (4 recovery options) | Built, tested incl. cabin-downgrade penalty |
| SOP RAG (4 docs), ATC signal (fake/live-gap) | Built, tested |
| T1–T4 escalation, confirmation gates, audit, PII-scrubbed feedback | Built, tested |
| Streamlit demo | Built (logic tested; UI not run here) |
| Live LLM planner, real METAR feed, real inventory | Planned |

## Knowledge

- [`knowledge/domain-notes.md`](knowledge/domain-notes.md) — distilled disruption-ops notes
- [`knowledge/architecture.md`](knowledge/architecture.md) — Mermaid diagrams
- [`docs/implementation-guide.md`](docs/implementation-guide.md) — adopter guide
- [`docs/interview-points.md`](docs/interview-points.md) — talk track
- [`docs/threat-model.md`](docs/threat-model.md) — STRIDE-lite

## Run it

```bash
python -m pytest tests/ -q          # 82 checks
python scripts/count_tests.py       # prints the real total
pip install streamlit && streamlit run demo/app.py
```

## Related repos

- `Jagadish-coldchain-logistics-agents`, `Jagadish-retail-ops-agents` — same FDE spine, different domains
- `Jagadish-agent-feedback-loop` — turns this repo's feedback into golden eval cases

---

*All data is synthetic and fictional (Meridian Air does not exist). Independent project, not affiliated with any airline. Crew-legality rules are simplified and illustrative, not regulatory.*
