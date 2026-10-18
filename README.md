# Jagadish-airline-disruption-agents

**Recruiter summary:** Airline disruptions cascade fast — one cancelled flight strands 42 passengers, ticks crew duty clocks toward illegality, and loses bags. This repo is an end-to-end disruption-operations agent: it answers open-ended ops questions over synthetic telemetry, enforces crew-legality rules with cited violations, ranks rebooking options with transparent scoring, and stops every safety-critical action at a human confirmation gate. Proof: 53 regression checks green; the demo finds 12 disrupted flights, 2 illegal crew pairings, and a 42-passenger rebooking backlog in one query.

## Problem → approach → outcome

**Problem.** Disruption desks juggle three questions at once — what broke, who is affected, what recovery is legal — under time pressure, where a wrong crew assignment grounds a flight.

**Approach.** A ReAct orchestrator fans out across five tools (text-to-SQL over read-only views, SOP RAG, crew-legality engine, rebooking optimizer, ATC/weather signal), classifies every event into T1–T4 escalation tiers, and gates T3/T4 actions on human confirmation. Every step lands in a hash-chained audit log.

**Outcome.** Deterministic, testable operations intelligence: ask "which flights are disrupted and are any crew pairings illegal?" and get cause-grouped counts plus the exact rules violated, with SOP citations.

## How it works

1. `airops/telemetry.py` builds a seeded SQLite world (fictional Meridian Air): flights, crew with duty clocks, passengers, baggage, recovery schedule.
2. `airops/text2sql.py` maps questions to 5 intents → fixed SELECT templates → `views.py` gateway (SEC-SELECT-01/02/03) → one self-correction retry, then explicit escalation.
3. `airops/crewlegality.py` evaluates every crew record against CL-DUTY-14 / CL-REST-10 / CL-FLIGHT-8 / CL-CONSEC-6 (simplified illustrative rules, not FAR 117), citing each violation.
4. `airops/rebooking.py` ranks recovery itineraries: `1.0*delay + 4.0*cabin + 6.0*conn-risk`, with the arithmetic shown.
5. `airops/sop_rag.py` retrieves SOP sections with `file §section` citations; says so when nothing matches.
6. `airops/escalation.py` tiers events; cancellations and duty-limit crew moves always need confirmation.
7. `airops/audit.py` + `airops/feedback.py` record everything tamper-evidently; feedback text is PII-scrubbed first.

Real run (seed 42):

```
>>> from airops import demo_helpers
>>> demo_helpers.disruption_summary()
{'by_cause': [{'delay_code': 'CREW', 'n': 6}, {'delay_code': 'WX', 'n': 3},
              {'delay_code': 'ATC', 'n': 2}, {'delay_code': 'MX', 'n': 1}],
 'illegal_pairings': 2, 'rebooking_backlog': 42}
>>> demo_helpers.rebook_demo('PAX-M207-00')['options'][0]
{'rec_id': 'REC-01', 'score': 3.3,
 'breakdown': '1.0*3.0h delay + 4.0*0 cabin + 6.0*0.05 conn-risk', ...}
```

## How this differs from coldchain/retail

Same FDE spine (SQLite telemetry, text-to-SQL, SOP RAG, escalation, audit), but the domain machinery is airline-specific: a **crew-legality rules engine** (duty/rest/flight-time limits with cited violations — meaningless outside aviation) and a **rebooking optimizer** (arrival-delay/cabin/connection-risk trade-offs). Cold-chain optimizes for temperature compliance; retail for demand signals; this repo optimizes for *legal recovery*.

## Guardrails and security controls

- SELECT-only SQL gateway with string-literal-aware write scanning (SEC-SELECT-01/02/03)
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

## Built / Written-not-run / Planned

| Item | Status |
|---|---|
| Telemetry, 5 text-to-SQL intents, gateway | Built, 53 checks green |
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
python -m pytest tests/ -q          # 53 checks, ~0.2s
python scripts/count_tests.py       # prints the real total
pip install streamlit && streamlit run demo/app.py
```

## Related repos

- `Jagadish-coldchain-logistics-agents`, `Jagadish-retail-ops-agents` — same FDE spine, different domains
- `Jagadish-agent-feedback-loop` — turns this repo's feedback into golden eval cases

---

*All data is synthetic and fictional (Meridian Air does not exist). Independent project, not affiliated with any airline. Crew-legality rules are simplified and illustrative, not regulatory.*
