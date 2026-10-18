"""Airport weather / ATC ground-stop signal.

FakeAtcSignal is deterministic and seeded. LiveAtcSignal is a stub with a
documented interface that returns an explicit gap result instead of
hallucinating when no live feed is configured.
"""

from __future__ import annotations


class SignalGap(Exception):
    """Raised when no live feed is available; never fabricate a signal."""


# Seeded fake feed: airport -> (condition, ground_stop_bool)
_FAKE_FEED = {
    "ORD": ("thunderstorms", True),
    "JFK": ("clear", False),
    "DFW": ("wind shear", True),
    "ATL": ("clear", False),
    "DEN": ("snow", False),
    "LAX": ("clear", False),
    "SEA": ("rain", False),
    "MIA": ("clear", False),
}


class FakeAtcSignal:
    """Deterministic fake ATC/weather feed."""

    def get(self, airport: str) -> dict:
        condition, ground_stop = _FAKE_FEED.get(airport.upper(), ("unknown", False))
        return {"airport": airport.upper(), "condition": condition,
                "ground_stop": ground_stop, "source": "fake"}


class LiveAtcSignal:
    """Live feed stub. Configure with a fetcher; otherwise raises SignalGap."""

    def __init__(self, fetcher=None):
        self._fetcher = fetcher

    def get(self, airport: str) -> dict:
        if self._fetcher is None:
            raise SignalGap(
                f"no live ATC feed configured for {airport}; refusing to invent one"
            )
        return self._fetcher(airport)
