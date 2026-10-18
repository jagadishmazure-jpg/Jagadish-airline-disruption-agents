"""Read-only views plus a SELECT-only SQL gateway with cited rule IDs.

SEC-SELECT-01: only SELECT statements may run.
SEC-SELECT-02: write keywords (INSERT/UPDATE/DELETE/DROP/...) are rejected;
    the scan is string-literal aware so words inside quotes don't false-positive.
SEC-SELECT-03: every query is capped at 100 rows (LIMIT appended when absent;
    rows beyond the cap are never fetched even if the caller asks for more).
SEC-SELECT-04: only the read-only views may be read. Enforced by a SQLite
    authorizer (airops/authz.py), so base tables, sqlite_master and pragmas
    are refused however they are spelled.
"""

from __future__ import annotations

import re
import sqlite3

from . import authz

VIEW_DDLS = {
    "v_disrupted_flights": """
        CREATE VIEW v_disrupted_flights AS
        SELECT flight_no, origin, dest, status, delay_minutes, delay_code, aircraft
        FROM flights WHERE status != 'on-time'
    """,
    "v_crew_status": """
        CREATE VIEW v_crew_status AS
        SELECT crew_id, role, base, duty_minutes, flight_minutes, rest_hours,
               consec_days, assigned_flight
        FROM crew
    """,
    "v_rebooking_queue": """
        CREATE VIEW v_rebooking_queue AS
        SELECT pax_id, name, flight_no, final_dest, cabin, status
        FROM passengers WHERE status != 'ok'
    """,
    "v_baggage_exceptions": """
        CREATE VIEW v_baggage_exceptions AS
        SELECT tag_id, pax_id, flight_no, status
        FROM baggage WHERE status != 'loaded'
    """,
    "v_delay_stats": """
        CREATE VIEW v_delay_stats AS
        SELECT delay_code, COUNT(*) AS n,
               ROUND(AVG(delay_minutes), 1) AS avg_delay_min
        FROM flights WHERE status = 'delayed' GROUP BY delay_code
    """,
}

WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|GRANT|ATTACH|DETACH)\b",
    re.IGNORECASE,
)
_LITERAL = re.compile(r"'(?:[^']|'')*'")


class GatewayError(ValueError):
    """Raised when a query violates the SELECT-only gateway."""


def _strip_literals(sql: str) -> str:
    return _LITERAL.sub("''", sql)


def ensure_select_only(sql: str, max_rows: int = 100) -> str:
    """Validate *sql* against the gateway rules; return a LIMIT-capped query."""
    cleaned = sql.strip().rstrip(";")
    if not re.match(r"(?i)^\s*select\b", cleaned):
        raise GatewayError("SEC-SELECT-01: only SELECT statements are allowed")
    if WRITE_KEYWORDS.search(_strip_literals(cleaned)):
        raise GatewayError("SEC-SELECT-02: write statements are not allowed")
    if not re.search(r"(?i)\blimit\s+\d+\s*$", cleaned):
        cleaned = f"{cleaned} LIMIT {max_rows}"  # SEC-SELECT-03
    return cleaned


def create_views(conn: sqlite3.Connection) -> None:
    for ddl in VIEW_DDLS.values():
        conn.execute(ddl.replace("CREATE VIEW", "CREATE VIEW IF NOT EXISTS", 1))
    conn.commit()


def run_query(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    """Run a gateway-checked SELECT; return rows as dicts."""
    safe = ensure_select_only(sql)
    with authz.views_only(conn, VIEW_DDLS) as denied:
        try:
            cur = conn.execute(safe, params)
        except sqlite3.DatabaseError:
            if denied:
                raise GatewayError(
                    f"SEC-SELECT-04: '{denied[0]}' is not one of the read-only views"
                ) from None
            raise
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(100)
    return [dict(zip(cols, row)) for row in rows]
