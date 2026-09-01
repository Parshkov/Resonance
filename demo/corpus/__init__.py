"""R7 demo corpus: consented sessions wrapping accepted Thought DNA.

Matching semantics stay in the accepted Resonance engine. This package only
stores presentation/consent metadata, validates it, and filters discovery.
"""

from .discovery import (
    CORPUS_SCHEMA_VERSION,
    discover,
    is_discoverable,
    load_sessions,
    presentation_view,
)
from .validate import CorpusValidationError, validate_corpus, validate_session

__all__ = [
    "CORPUS_SCHEMA_VERSION",
    "CorpusValidationError",
    "discover",
    "is_discoverable",
    "load_sessions",
    "presentation_view",
    "validate_corpus",
    "validate_session",
]
