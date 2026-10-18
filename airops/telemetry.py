"""Synthetic airline telemetry on SQLite (fictional Meridian Air, seed 42).

Tables: flights, crew, passengers, baggage, plus a recovery schedule used by
the rebooking optimizer. Deterministic anchors are baked in so tests and the
demo always have something to find.
"""

from __future__ import annotations

import random
import sqlite3

SEED = 42

SCHEMA = """
CREATE TABLE flights (
    flight_no   TEXT PRIMARY KEY,
    origin      TEXT NOT NULL,
    dest        TEXT NOT NULL,
    status      TEXT NOT NULL,      -- on-time | delayed | cancelled | diverted
    delay_minutes INTEGER NOT NULL DEFAULT 0,
    delay_code  TEXT,               -- WX | MX | CREW | ATC | null
    aircraft    TEXT NOT NULL
);
CREATE TABLE crew (
    crew_id        TEXT PRIMARY KEY,
    role           TEXT NOT NULL,   -- captain | fo | fa
    base           TEXT NOT NULL,
    duty_minutes   INTEGER NOT NULL,  -- minutes into current duty period
    flight_minutes INTEGER NOT NULL,  -- flight time this duty period
    rest_hours     REAL NOT NULL,     -- rest hours before current duty
    consec_days    INTEGER NOT NULL,  -- consecutive duty days
    assigned_flight TEXT
);
CREATE TABLE passengers (
    pax_id      TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    flight_no   TEXT NOT NULL,
    final_dest  TEXT NOT NULL,
    cabin       TEXT NOT NULL,       -- Y | J
    status      TEXT NOT NULL        -- ok | misconnected | needs-rebook
);
CREATE TABLE baggage (
    tag_id    TEXT PRIMARY KEY,
    pax_id    TEXT NOT NULL,
    flight_no TEXT NOT NULL,
    status    TEXT NOT NULL          -- loaded | mishandled | tracing
);
CREATE TABLE recovery_schedule (
    rec_id      TEXT PRIMARY KEY,
    origin      TEXT NOT NULL,
    dest        TEXT NOT NULL,
    dep_offset_h REAL NOT NULL,      -- hours after the disrupted flight
    arr_delay_h  REAL NOT NULL,      -- extra arrival delay vs original plan
    cabin_avail  TEXT NOT NULL,      -- Y | J | YJ
    conn_risk    REAL NOT NULL       -- 0..1 connection risk score
);
"""

AIRPORTS = ["ORD", "JFK", "DFW", "ATL", "DEN", "LAX", "SEA", "MIA"]
DELAY_CODES = ["WX", "MX", "CREW", "ATC"]


def build_db(seed: int = SEED) -> sqlite3.Connection:
    """Build and return a fresh in-memory telemetry DB."""
    rng = random.Random(seed)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    # --- flights: 24 scheduled, mix of statuses ---
    flights = []
    n = 0
    for i, (o, d) in enumerate(
        [(a, b) for a in AIRPORTS for b in AIRPORTS if a != b][:24]
    ):
        n += 1
        flight_no = f"MA-{100 + n}"
        roll = rng.random()
        if roll < 0.55:
            status, delay, code = "on-time", 0, None
        elif roll < 0.75:
            status, delay, code = "delayed", rng.choice([25, 40, 55, 90, 130]), rng.choice(DELAY_CODES)
        elif roll < 0.88:
            status, delay, code = "cancelled", 0, rng.choice(["WX", "MX", "CREW"])
        else:
            status, delay, code = "diverted", rng.choice([60, 120]), rng.choice(["WX", "ATC"])
        flights.append((flight_no, o, d, status, delay, code, f"N{rng.randint(100, 999)}MA"))
    conn.executemany("INSERT INTO flights VALUES (?,?,?,?,?,?,?)", flights)

    # --- deterministic anchors ---
    # Anchor 1: MA-207 cancelled for weather with 42 misconnected passengers.
    conn.execute(
        "INSERT OR REPLACE INTO flights VALUES (?,?,?,?,?,?,?)",
        ("MA-207", "ORD", "JFK", "cancelled", 0, "WX", "N207MA"),
    )
    # Anchor 2: MA-310 heavily delayed for crew reasons.
    conn.execute(
        "INSERT OR REPLACE INTO flights VALUES (?,?,?,?,?,?,?)",
        ("MA-310", "DFW", "LAX", "delayed", 165, "CREW", "N310MA"),
    )

    # --- crew: 16 members ---
    crew = []
    roles = ["captain", "fo", "fa", "fa"]
    for i in range(16):
        cid = f"C-{1000 + i}"
        crew.append(
            (
                cid,
                roles[i % 4],
                rng.choice(AIRPORTS),
                rng.randint(120, 700),          # duty minutes
                rng.randint(60, 420),           # flight minutes
                round(rng.uniform(10.5, 16.0), 1),
                rng.randint(1, 5),
                rng.choice([f[0] for f in flights]),
            )
        )
    conn.executemany("INSERT INTO crew VALUES (?,?,?,?,?,?,?,?)", crew)
    # Anchor 3: C-ILLEGAL-01 exceeds the 14h duty limit (15.5h = 930 min).
    conn.execute(
        "INSERT OR REPLACE INTO crew VALUES (?,?,?,?,?,?,?,?)",
        ("C-ILLEGAL-01", "captain", "ORD", 930, 430, 12.0, 3, "MA-207"),
    )
    # Anchor 4: C-REST-02 had only 8h rest (rule needs 10h).
    conn.execute(
        "INSERT OR REPLACE INTO crew VALUES (?,?,?,?,?,?,?,?)",
        ("C-REST-02", "fo", "ORD", 300, 180, 8.0, 2, "MA-310"),
    )

    # --- passengers: 42 misconnected on MA-207 + others ---
    pax = []
    for i in range(42):
        pax.append(
            (
                f"PAX-M207-{i:02d}",
                f"Traveler {i + 1}",
                "MA-207",
                "JFK",
                "Y" if i % 7 else "J",
                "misconnected" if i % 3 else "needs-rebook",
            )
        )
    for i in range(60):
        pax.append(
            (
                f"PAX-{2000 + i}",
                f"Traveler {100 + i}",
                rng.choice([f[0] for f in flights]),
                rng.choice(AIRPORTS),
                rng.choice(["Y", "Y", "Y", "J"]),
                "ok",
            )
        )
    conn.executemany("INSERT INTO passengers VALUES (?,?,?,?,?,?)", pax)

    # --- baggage ---
    bags = []
    for i in range(30):
        bags.append(
            (f"BAG-{3000 + i}", f"PAX-{2000 + i}", rng.choice([f[0] for f in flights]), "loaded")
        )
    # Anchor 5: mishandled bag on the cancelled flight.
    bags.append(("BAG-EXC-01", "PAX-M207-00", "MA-207", "mishandled"))
    bags.append(("BAG-EXC-02", "PAX-M207-01", "MA-207", "tracing"))
    conn.executemany("INSERT INTO baggage VALUES (?,?,?,?)", bags)

    # --- recovery schedule ORD->JFK (for the rebooking optimizer) ---
    rec = [
        ("REC-01", "ORD", "JFK", 3.0, 3.0, "YJ", 0.05),
        ("REC-02", "ORD", "JFK", 5.5, 5.5, "Y", 0.10),
        ("REC-03", "ORD", "JFK", 4.0, 6.5, "YJ", 0.55),  # tight connection
        ("REC-04", "ORD", "JFK", 9.0, 9.0, "Y", 0.02),
    ]
    conn.executemany("INSERT INTO recovery_schedule VALUES (?,?,?,?,?,?,?)", rec)
    conn.commit()
    return conn


def get_conn() -> sqlite3.Connection:
    """Default shared in-memory DB (fresh per call)."""
    return build_db()
