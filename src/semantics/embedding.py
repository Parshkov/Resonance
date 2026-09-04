"""Optional node-embedding seam.

The engine's default semantics are the deterministic lexicon + stems in
``similarity.py``. This module exists so an operator can plug in a *non-LLM*
neural sentence encoder later (a small local model) without touching the
matcher: register a provider and ``label_vector`` routes through it.

The default provider is a hashed stem/concept/trigram vector so that the
seam is exercised in tests and produces the same ordering as ``compare``.
No provider is loaded from the network, ever.
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol, Sequence

from .similarity import abstract_concepts, stems, _trigrams

DIM = 256


class LabelEmbedder(Protocol):
    name: str

    def embed(self, label: str) -> Sequence[float]: ...


def _slot(token: str) -> int:
    return int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=4).digest(), "big") % DIM


class HashedFeatureEmbedder:
    """Deterministic default: stems (w=1.0), concepts (w=1.5), trigrams (w=0.3)."""

    name = "hashed-feature/0.1"

    def embed(self, label: str) -> list[float]:
        vec = [0.0] * DIM
        for s in stems(label):
            vec[_slot("s:" + s)] += 1.0
        for c in abstract_concepts(label):
            vec[_slot("c:" + c)] += 1.5
        for g, n in _trigrams(label).items():
            vec[_slot("g:" + g)] += 0.3 * n
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm else vec


_PROVIDER: LabelEmbedder = HashedFeatureEmbedder()


def set_embedder(provider: LabelEmbedder | None) -> None:
    global _PROVIDER
    _PROVIDER = provider or HashedFeatureEmbedder()


def embedder_name() -> str:
    return _PROVIDER.name


def label_vector(label: str) -> Sequence[float]:
    return _PROVIDER.embed(label)


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0
