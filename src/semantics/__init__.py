"""Deterministic, LLM-free label semantics for the Resonance engine."""

from .lexicon import CONCEPTS, LEXICON_VERSION, ROLE_HINTS, is_domain_concept
from .pii import SCRUB_VERSION, contains_pii, scrub
from .similarity import (
    SEMANTICS_VERSION,
    LabelSimilarity,
    abstract_concepts,
    abstract_signature,
    compare,
    concept_similarity,
    concepts,
    domain_concepts,
    label_similarity,
    role_hint,
    stems,
    surface_similarity,
)
from .stem import stem
from . import neural

# The label encoder is opt-in (RESONANCE_EMBEDDER=<model directory>). Loaded
# here so every reader of `compare` sees the same answer, and best-effort:
# the server validates the variable itself and refuses to start on a bad
# one, so a quiet fallback here cannot hide a misconfigured deployment.
try:
    neural.activate_from_environment()
except neural.NeuralUnavailable:
    pass

__all__ = [
    "CONCEPTS", "LEXICON_VERSION", "ROLE_HINTS", "SEMANTICS_VERSION", "SCRUB_VERSION",
    "LabelSimilarity", "abstract_concepts", "abstract_signature", "compare", "concept_similarity",
    "concepts", "contains_pii", "domain_concepts", "is_domain_concept", "label_similarity",
    "role_hint", "scrub", "stem", "stems", "surface_similarity", "neural",
]
