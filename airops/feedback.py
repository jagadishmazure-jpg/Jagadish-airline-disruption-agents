"""User feedback capture with PII scrubbing before storage.

Thumbs up/down plus free-text corrections. Every record is scrubbed with
pii.scrub() first, then appended to the shared audit chain so feedback is
tamper-evident alongside operational events.
"""

from __future__ import annotations

from . import pii


class FeedbackError(ValueError):
    """Raised for malformed feedback (bad rating, empty correction, ...)."""


def capture_feedback(audit_log, *, session_id: str, turn_id: str,
                     rating: str, correction: str = "") -> dict:
    """Validate, scrub, and record feedback. Returns the audit entry."""
    if rating not in ("up", "down"):
        raise FeedbackError(f"rating must be 'up' or 'down', got {rating!r}")
    if not session_id or not str(session_id).strip():
        raise FeedbackError("session_id is required")
    if not turn_id or not str(turn_id).strip():
        raise FeedbackError("turn_id is required")
    if rating == "down" and not correction.strip():
        raise FeedbackError("thumbs-down requires a non-empty correction")
    scrubbed, redactions = pii.scrub(correction)
    return audit_log.record("user", "user_feedback", {
        "session_id": session_id,
        "turn_id": turn_id,
        "rating": rating,
        "correction": scrubbed,
        "pii_redactions": redactions,
    })


def list_feedback(audit_log, session_id: str | None = None) -> list[dict]:
    """Return feedback entries from the audit chain, optionally by session."""
    out = []
    for e in audit_log.entries:
        if e["action"] != "user_feedback":
            continue
        if session_id is not None and e["details"].get("session_id") != session_id:
            continue
        out.append(e)
    return out
