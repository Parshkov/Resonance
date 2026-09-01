"""Deterministic engine + registry over the accepted R7 demo corpus.

Hidden sessions are NEVER indexed (R7 rule via index_discoverable) and get no
registry profile -- two independent layers keep them out.
"""

from __future__ import annotations

from demo.corpus.discovery import index_discoverable, load_sessions
from src.engine import ResonanceEngine

from ..metadata import ConsentRegistry

FLAGSHIP_SESSION_ID = "ses-aria-plasma-lens"


def build(sessions=None):
    records = list(sessions) if sessions is not None else load_sessions()
    engine = ResonanceEngine()
    index_discoverable(engine, records)
    registry = ConsentRegistry.from_r7_sessions(records)
    by_session = {r["session_id"]: r for r in records}
    return engine, registry, by_session


def flagship_query(by_session):
    from src.graph import ThoughtGraph
    return ThoughtGraph.from_dict(by_session[FLAGSHIP_SESSION_ID]["thought_dna"])
