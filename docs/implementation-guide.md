# Implementation guide

For adopters wiring this pattern into a real operations desk.

## 1. Replace the telemetry
`airops/telemetry.py::build_db` is the only synthetic seam. Point it at your
warehouse (read replica!) and map columns onto the five view shapes in
`airops/views.py`. Keep the views read-only: the SELECT-only gateway
(`SEC-SELECT-01/02/03`) is a safety control, not a suggestion.

## 2. Calibrate the legality rules
`airops/crewlegality.py::RULES` are simplified demo limits. Replace them with
your airline's actual duty rules (or FAR 117 logic) — the engine shape
(rule id, description, limit, field, comparator) stays the same, and every
violation still cites the exact rule.

## 3. Feed the rebooking optimizer
`recovery_schedule` should come from your inventory system. The scoring
weights (`W_DELAY`, `W_CABIN`, `W_CONN`) are the product decision: tune them
with ops, and keep the `breakdown` string — agents must show their arithmetic.

## 4. Wire the live ATC feed
Implement the `fetcher` callable for `LiveAtcSignal` against your METAR/ATCSCC
source. Until then the explicit `SignalGap` is the correct behavior: the
system says it doesn't know rather than inventing weather.

## 5. Human gates
`ALWAYS_GATED` in `airops/escalation.py` lists actions that must stop for a
human. Review it with your safety team before any production use.

## 6. Feedback loop
`feedback.py` already scrubs PII. Pipe the audit chain into the
`Jagadish-agent-feedback-loop` repo's miner to turn corrections into golden
eval cases.
