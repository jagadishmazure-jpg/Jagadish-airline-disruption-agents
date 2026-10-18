"""Rebooking optimizer (domain differentiator).

Ranks recovery itineraries for a misconnected passenger by a transparent
score: arrival delay dominates, then cabin mismatch, then connection risk.

score = 1.0 * arr_delay_h + 4.0 * cabin_mismatch + 6.0 * conn_risk
Lower is better. Every ranked option carries its component breakdown.
"""

from __future__ import annotations

import sqlite3

W_DELAY = 1.0
W_CABIN = 4.0
W_CONN = 6.0


def _cabin_mismatch(pax_cabin: str, avail: str) -> int:
    """0 if the passenger's cabin is available, 1 if downgraded."""
    if pax_cabin == "J":
        return 0 if "J" in avail else 1
    return 0  # Y passengers fit anywhere


def rank_options(conn: sqlite3.Connection, origin: str, dest: str,
                 pax_cabin: str = "Y") -> list[dict]:
    """Rank recovery options ORD->dest; best (lowest score) first."""
    rows = conn.execute(
        "SELECT rec_id, origin, dest, dep_offset_h, arr_delay_h, cabin_avail, conn_risk "
        "FROM recovery_schedule WHERE origin = ? AND dest = ?",
        (origin, dest),
    ).fetchall()
    ranked = []
    for rec_id, _o, _d, dep_h, arr_h, avail, risk in rows:
        mismatch = _cabin_mismatch(pax_cabin, avail)
        score = W_DELAY * arr_h + W_CABIN * mismatch + W_CONN * risk
        ranked.append({
            "rec_id": rec_id,
            "dep_in_h": dep_h,
            "arr_delay_h": arr_h,
            "cabin_avail": avail,
            "conn_risk": risk,
            "cabin_mismatch": mismatch,
            "score": round(score, 2),
            "breakdown": (f"{W_DELAY}*{arr_h}h delay + {W_CABIN}*{mismatch} cabin "
                          f"+ {W_CONN}*{risk} conn-risk"),
        })
    ranked.sort(key=lambda r: r["score"])
    return ranked


def best_option(conn: sqlite3.Connection, origin: str, dest: str,
                pax_cabin: str = "Y") -> dict | None:
    """Return the top-ranked recovery option, or None if none exist."""
    ranked = rank_options(conn, origin, dest, pax_cabin)
    return ranked[0] if ranked else None
