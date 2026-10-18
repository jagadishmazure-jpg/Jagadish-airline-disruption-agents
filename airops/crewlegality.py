"""Crew-legality rules engine (domain differentiator).

Simplified, illustrative duty rules for the fictional Meridian Air — these are
NOT real FAR Part 117 regulations, and the module docstring says so. Every
violation cites the exact rule that fired, in evaluation order.

Rules:
  CL-DUTY-14   duty period may not exceed 14:00 hours
  CL-REST-10   minimum 10:00 hours rest between duty periods
  CL-FLIGHT-8  flight time within a duty period capped at 8:00 hours
  CL-CONSEC-6  no more than 6 consecutive duty days
"""

from __future__ import annotations

from dataclasses import dataclass

# (rule_id, description, limit, field, comparator)
# comparator: "max" -> value must be <= limit; "min" -> value must be >= limit
RULES = [
    ("CL-DUTY-14", "Duty period may not exceed 14:00 hours", 14 * 60, "duty_minutes", "max"),
    ("CL-REST-10", "Minimum 10:00 hours rest between duty periods", 10.0, "rest_hours", "min"),
    ("CL-FLIGHT-8", "Flight time within a duty period capped at 8:00 hours", 8 * 60, "flight_minutes", "max"),
    ("CL-CONSEC-6", "No more than 6 consecutive duty days", 6, "consec_days", "max"),
]


@dataclass(frozen=True)
class Violation:
    rule_id: str
    description: str
    detail: str


def evaluate_crew(crew: dict) -> list[Violation]:
    """Evaluate one crew record; return violations in rule-evaluation order."""
    out: list[Violation] = []
    for rule_id, desc, limit, field, comp in RULES:
        value = crew[field]
        if comp == "max" and value > limit:
            out.append(Violation(rule_id, desc,
                                f"{field}={value} exceeds limit {limit}"))
        elif comp == "min" and value < limit:
            out.append(Violation(rule_id, desc,
                                f"{field}={value} below minimum {limit}"))
    return out


def find_illegal_pairings(crew_rows: list[dict]) -> list[dict]:
    """Return crew with violations, each citing the exact rules fired."""
    illegal = []
    for row in crew_rows:
        violations = evaluate_crew(row)
        if violations:
            illegal.append({
                "crew_id": row["crew_id"],
                "role": row["role"],
                "assigned_flight": row["assigned_flight"],
                "violations": [(v.rule_id, v.description, v.detail) for v in violations],
            })
    return illegal
