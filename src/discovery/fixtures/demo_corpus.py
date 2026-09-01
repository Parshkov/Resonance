"""Deterministic demo corpus builder (PROVISIONAL, pending R7-CORPUS freeze).

Six consented-metadata sessions whose texts run through the accepted cue
extractor: the flagship battery query, a discoverable cross-domain analogue,
a polarity-flip near-duplicate, two noise sessions -- and one HIDDEN session
that is structurally resonant, present precisely so tests can prove hidden
records are absent from matches AND uninferable from aggregation counts.
"""

from __future__ import annotations

from src.engine import ResonanceEngine
from .metadata_payload import METADATA_PAYLOAD  # noqa: F401 (re-export)

TEXTS = {
    "s-battery": ("Strong heat causes degradation. Degradation causes failure. "
                  "Heavy load causes strong heat. Active cooling prevents strong heat. "
                  "Failure causes replacement cost."),
    "s-org": ("Rapid growth causes coordination loss. Coordination loss causes collapse. "
              "Heavy workload causes rapid growth. Clear delegation prevents rapid growth. "
              "Collapse causes restructuring cost."),
    "s-flip": ("Strong heat prevents degradation. Degradation causes failure. "
               "Heavy load causes strong heat. Active cooling prevents strong heat. "
               "Failure causes replacement cost."),
    "s-noise-rain": "Rain causes floods. Floods cause damage.",
    "s-noise-skill": "Practice causes skill. Skill prevents mistakes.",
    "s-eco": ("Warm water causes algae growth. Algae growth causes oxygen loss. "
              "Farm runoff causes warm water. Deep currents prevent warm water. "
              "Oxygen loss causes cleanup cost."),
    "s-para": ("Intense heat causes wear. Wear causes breakdown. "
               "Big load causes intense heat. Good cooling prevents intense heat. "
               "Breakdown causes replacement cost."),
    "s-hidden-market": ("Fast expansion causes control loss. Control loss causes breakdown. "
                        "Big demand causes fast expansion. Strict process prevents fast expansion. "
                        "Breakdown causes recovery cost."),
}


def build_engine() -> tuple[ResonanceEngine, dict[str, str]]:
    """Extract + index every session deterministically; returns the engine and
    session_id -> thought_id mapping (extraction ids are content-derived)."""
    engine = ResonanceEngine()
    thought_ids: dict[str, str] = {}
    for session_id, text in sorted(TEXTS.items()):
        graph = engine.ingest(text, source_id=session_id)
        engine.index(graph)
        thought_ids[session_id] = graph.thought_id
    return engine, thought_ids
