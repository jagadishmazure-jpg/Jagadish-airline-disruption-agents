# Domain notes: airline disruption management

Distilled from airline operations practice (IATA delay-code conventions,
crew-duty concepts). All numbers below describe this repo's synthetic data.

## The problem
A single cancellation cascades: 42 misconnected passengers need rebooking,
crew duty clocks keep ticking toward illegality, and bags miss their flights.
The operations desk must answer three questions fast: what broke, who is
affected, and what is the legal recovery.

## Key domain concepts
- **Delay codes** (WX/MX/CREW/ATC): the industry shorthand for root cause.
  Every disruption answer in this repo is grouped by cause code first.
- **Crew legality**: duty-time, rest, flight-time, and consecutive-day limits.
  An illegal pairing grounds a flight — the engine here cites the exact rule
  (CL-DUTY-14 etc.). Rules are simplified company rules for the demo, not
  real FAR Part 117 regulation.
- **Misconnection vs cancellation**: a delayed flight misconnects passengers;
  a cancelled flight strands them. The rebooking queue tracks both states.
- **Recovery ranking**: arrival delay dominates, then cabin downgrade, then
  connection risk. The optimizer shows its arithmetic, never just a pick.

## Why this is agentic
The questions are open-ended ("what broke this morning?") but the actions
are safety-critical (cancel a flight, reassign crew). The ReAct loop plans
across telemetry, SOPs, legality, and rebooking tools; T3/T4 actions stop at
a human confirmation gate. The audit chain makes every decision replayable.
