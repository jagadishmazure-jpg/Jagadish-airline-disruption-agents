# Threat model (STRIDE-lite)

| Threat | Where | Mitigation |
|---|---|---|
| SQL injection via NL question | text-to-SQL planner | Fixed templates per intent; SELECT-only gateway (SEC-SELECT-01/02/03); parameterized params; errors never echo row data |
| Prompt injection via SOP docs | RAG retriever | SOPs are local first-party files; retrieval is TF-IDF (no LLM); citations bound to file+section |
| Unauthorized action (cancel flight) | Escalation tiers | T3/T4 + ALWAYS_GATED require human confirmation; gate timeout denies by default (no approver -> timeout) |
| Audit tampering | AuditLog | SHA-256 hash chain; verify_chain() detects modification, drops, reordering |
| PII leakage in feedback | feedback.py | pii.scrub() redacts email/phone (incl. `(555) 123-4567`)/SSN before storage and keeps dates; redaction count recorded |
| Hallucinated external data | weathersignal | LiveAtcSignal raises SignalGap when unconfigured; fake backend is labelled fake |
| Illegal crew assignment | crewlegality | Engine blocks on cited rules; reassignment over duty limits is ALWAYS_GATED |

## Out of scope
Model-level threats (this repo runs no LLM; the planner is deterministic).
Network security of the demo UI. Real FAR 117 compliance (rules here are
simplified and labelled as such).
