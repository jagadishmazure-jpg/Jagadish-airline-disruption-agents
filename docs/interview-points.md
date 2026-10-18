# Interview points

- **Why this repo:** airline disruptions are the canonical "open-ended question,
  safety-critical action" problem — perfect for demonstrating agentic patterns
  with real guardrails.
- **Differentiator 1 — crew legality:** a rules engine with cited rule IDs
  (CL-DUTY-14 etc.). I can explain why the engine shape (id, description,
  limit, field, comparator) makes violations auditable, and why the rules are
  labelled illustrative rather than claimed as FAR 117.
- **Differentiator 2 — rebooking optimizer:** transparent scoring
  (1.0*delay + 4.0*cabin + 6.0*conn-risk) with a breakdown string. The product
  decision is in the weights; the agent shows its arithmetic.
- **Safety:** SELECT-only gateway with string-literal-aware write scanning
  (no false positives on words like 'deleted' inside quotes), T3/T4
  confirmation gates, hash-chained audit, PII scrubbing before feedback
  storage.
- **Failure modes I've handled:** intent-ordering collisions (specific
  intents first), self-correction retry then explicit escalation, live-feed
  gap instead of hallucinated weather.
- **Numbers (synthetic, seed 42):** 82 regression checks green; demo shows
  12 disrupted flights (CREW 6, WX 3, ATC 2, MX 1), 2 illegal pairings,
  42-passenger rebooking backlog.
