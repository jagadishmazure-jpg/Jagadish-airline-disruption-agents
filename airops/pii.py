"""PII scrubber for free-text feedback.

Email addresses, phone-like digit runs, and SSN-like patterns are replaced
with typed placeholders before anything is stored. The scrubber reports how
many redactions it made so callers can audit the behavior.
"""

from __future__ import annotations

import re

_PATTERNS = [
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "[EMAIL]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\+?\d[\d\s().-]{8,}\d"), "[PHONE]"),
]


def scrub(text: str) -> tuple[str, int]:
    """Return (scrubbed_text, redaction_count)."""
    count = 0
    out = text
    for pattern, placeholder in _PATTERNS:
        out, n = pattern.subn(placeholder, out)
        count += n
    return out, count
