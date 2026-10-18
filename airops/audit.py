"""Hash-chained audit log.

Each entry commits to the previous entry's hash; verify_chain() detects any
tampering (modified entry, dropped entry, reordered entry).
"""

from __future__ import annotations

import hashlib
import json
import time


def _hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AuditLog:
    def __init__(self):
        self.entries: list[dict] = []

    def record(self, actor: str, action: str, details: dict | None = None) -> dict:
        prev = self.entries[-1]["hash"] if self.entries else "GENESIS"
        entry = {
            "seq": len(self.entries),
            "ts": time.time(),
            "actor": actor,
            "action": action,
            "details": details or {},
            "prev": prev,
        }
        entry["hash"] = _hash(json.dumps(
            {k: entry[k] for k in ("seq", "ts", "actor", "action", "details", "prev")},
            sort_keys=True))
        self.entries.append(entry)
        return entry

    def verify_chain(self) -> tuple[bool, str]:
        prev = "GENESIS"
        for e in self.entries:
            if e["prev"] != prev:
                return False, f"broken link at seq {e['seq']}"
            recomputed = _hash(json.dumps(
                {k: e[k] for k in ("seq", "ts", "actor", "action", "details", "prev")},
                sort_keys=True))
            if recomputed != e["hash"]:
                return False, f"tampered entry at seq {e['seq']}"
            prev = e["hash"]
        return True, f"{len(self.entries)} entries verified"
