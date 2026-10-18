"""Jagadish-airline-disruption-agents: end-to-end airline disruption management.

Synthetic telemetry, text-to-SQL over read-only views, SOP RAG, crew-legality
rules engine, rebooking optimizer, escalation tiers, hash-chained audit.
All data is fictional and generated deterministically (seed 42).
"""

from . import (
    audit,
    crewlegality,
    demo_helpers,
    escalation,
    feedback,
    orchestrator,
    pii,
    rebooking,
    sop_rag,
    telemetry,
    text2sql,
    views,
    weathersignal,
)

__all__ = [
    "audit",
    "crewlegality",
    "demo_helpers",
    "escalation",
    "feedback",
    "orchestrator",
    "pii",
    "rebooking",
    "sop_rag",
    "telemetry",
    "text2sql",
    "views",
    "weathersignal",
]
