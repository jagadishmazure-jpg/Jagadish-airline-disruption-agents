"""T1-T4 escalation tiers plus confirmation gates.

T1 info: log only.  T2 watch: log + flag for review.
T3 act: needs a human confirmation before the action runs.
T4 critical: page immediately AND needs confirmation.

ConfirmationGate.decide(action) -> "approved" | "denied" | "timeout".
Flight cancellations and crew reassignments that would breach a duty
limit always require confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ConfirmationGate:
    """Deterministic gate; the approver callable is injected (tests approve/deny)."""

    approver: Callable[[dict], bool] | None = None

    def decide(self, action: dict) -> str:
        if self.approver is None:
            return "timeout"
        try:
            return "approved" if self.approver(action) else "denied"
        except Exception:
            return "timeout"


TIERS = {
    "T1": "informational: log only",
    "T2": "watch: log and flag for review",
    "T3": "act: requires human confirmation",
    "T4": "critical: page immediately, requires human confirmation",
}

# actions that always need confirmation, by name
ALWAYS_GATED = {"cancel_flight", "reassign_crew_over_duty_limit"}


def tier_for(event: dict) -> str:
    """Classify an event dict {kind, severity} into a tier."""
    kind = event.get("kind", "")
    severity = event.get("severity", "low")
    if kind in ("cancellation", "illegal_crew") or severity == "critical":
        return "T4"
    if kind in ("rebooking", "crew_reassign") or severity == "high":
        return "T3"
    if severity == "medium":
        return "T2"
    return "T1"


@dataclass
class Escalation:
    tier: str
    action: dict
    gate_decision: str | None = None
    log: list = field(default_factory=list)

    def run(self, gate: ConfirmationGate) -> "Escalation":
        needs_gate = self.tier in ("T3", "T4") or self.action.get("name") in ALWAYS_GATED
        if needs_gate:
            self.gate_decision = gate.decide(self.action)
            self.log.append(f"gate:{self.gate_decision}")
        else:
            self.log.append("no-gate-needed")
        return self
