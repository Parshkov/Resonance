"""Deterministic label semantics: stems, concept classes, similarity.

Three independent signals, all inspectable and stdlib-only:

* ``surface``  - lexical overlap of stems plus character-trigram cosine.
                 High for paraphrase / inflection / "rephrased X".
* ``concept``  - overlap of abstract concept classes from the lexicon.
                 High for "heat accumulation" vs "backlog pileup" even when no
                 word is shared. Domain classes are excluded from this signal.
* ``domain``   - overlap of domain-anchor classes (battery vs battery).

``label_similarity`` fuses them into one [0,1] number for alignment; the
separate signals are what lets scoring tell synonymy (surface high) from
analogy (concept high, surface low) from template coincidence (both low).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from .lexicon import LEXICON_VERSION, LONGEST_PHRASE, PHRASE_INDEX, ROLE_HINTS, class_weight, is_domain_concept, relatedness
from .stem import stem

SEMANTICS_VERSION = "resonance-semantics/0.2.0+" + LEXICON_VERSION

STOPWORDS = frozenset(
    "a an the of in on at to for from by with without and or but nor so yet as is are was were be been "
    "being am do does did doing have has had having it its this that these those there here than then "
    "into onto over under up down out off about above below between through during before after "
    "again further once very too own same other some such no not only just also can could may might "
    "must shall should will would our we you your they their them his her him he she i me my mine "
    "ours yours theirs what which who whom whose when where why how all any both each few more most "
    "s t d ll re ve".split()
)


def split_words(text: str) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    for ch in text.lower():
        if ch.isalnum():
            cur.append(ch)
        else:
            if cur:
                out.append("".join(cur))
                cur = []
    if cur:
        out.append("".join(cur))
    return out


@lru_cache(maxsize=65536)
def stems(label: str) -> tuple[str, ...]:
    """Content stems in order (stopwords removed, duplicates kept)."""
    return tuple(stem(w) for w in split_words(label) if w not in STOPWORDS)


@lru_cache(maxsize=65536)
def concepts(label: str) -> frozenset[str]:
    """All lexicon classes realised by the label (longest-phrase-first greedy)."""
    words = split_words(label)
    stemmed = [stem(w) for w in words]
    found: set[str] = set()
    i = 0
    n = len(stemmed)
    while i < n:
        matched = 0
        for length in range(min(LONGEST_PHRASE, n - i), 0, -1):
            key = tuple(stemmed[i : i + length])
            hit = PHRASE_INDEX.get(key)
            if hit:
                found |= hit
                matched = length
                break
        i += matched if matched else 1
    return frozenset(found)


def abstract_concepts(label: str) -> frozenset[str]:
    return frozenset(c for c in concepts(label) if not is_domain_concept(c))


def domain_concepts(label: str) -> frozenset[str]:
    return frozenset(c for c in concepts(label) if is_domain_concept(c))


def role_hint(label: str) -> str | None:
    """Majority role hint from the label's abstract concepts, or None."""
    votes: dict[str, int] = {}
    for c in abstract_concepts(label):
        hint = ROLE_HINTS.get(c)
        if hint:
            votes[hint] = votes.get(hint, 0) + 1
    if not votes:
        return None
    return sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


@lru_cache(maxsize=65536)
def _trigrams(label: str) -> dict[str, int]:
    text = " " + " ".join(split_words(label)) + " "
    out: dict[str, int] = {}
    for i in range(len(text) - 2):
        g = text[i : i + 3]
        out[g] = out.get(g, 0) + 1
    return out


def _cosine(a: dict[str, int], b: dict[str, int]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def soft_overlap(a: frozenset[str], b: frozenset[str]) -> float:
    """Soft Jaccard over concept classes using lexicon relatedness.

    Each class on either side contributes its best relatedness to the other
    side; the mean over |a|+|b| slots is 1.0 for identical sets, 0.0 when no
    class is related, and in between for neighbouring notions.
    """
    if not a or not b:
        return 0.0
    total = 0.0
    weight_sum = 0.0
    for x in a:
        w = class_weight(x)
        total += w * max(relatedness(x, y) for y in b)
        weight_sum += w
    for y in b:
        w = class_weight(y)
        total += w * max(relatedness(x, y) for x in a)
        weight_sum += w
    return total / weight_sum if weight_sum else 0.0


def _jaccard(a: frozenset | set, b: frozenset | set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass(frozen=True, slots=True)
class LabelSimilarity:
    surface: float   # stems / trigrams
    concept: float   # abstract concept overlap
    domain: float    # domain anchor overlap
    fused: float     # single number for alignment affinity


@lru_cache(maxsize=262144)
def compare(a: str, b: str) -> LabelSimilarity:
    sa, sb = frozenset(stems(a)), frozenset(stems(b))
    lex = _jaccard(sa, sb)
    tri = _cosine(_trigrams(a), _trigrams(b))
    # trigram cosine is generous on short strings; discount it and require
    # some lexical support before it can claim near-identity.
    surface = max(lex, 0.85 * tri if tri > 0.5 else 0.6 * tri)
    ca, cb = abstract_concepts(a), abstract_concepts(b)
    concept = soft_overlap(ca, cb)
    da, db = domain_concepts(a), domain_concepts(b)
    domain = _jaccard(da, db)
    fused = max(surface, 0.9 * concept, 0.5 * domain, 0.5 * surface + 0.5 * concept)
    return LabelSimilarity(surface=surface, concept=concept, domain=domain, fused=min(1.0, fused))


def label_similarity(a: str, b: str) -> float:
    return compare(a, b).fused


def surface_similarity(a: str, b: str) -> float:
    return compare(a, b).surface


def concept_similarity(a: str, b: str) -> float:
    return compare(a, b).concept


def abstract_signature(label: str) -> tuple[str, ...]:
    """Sorted abstract concept classes; empty when the lexicon is silent."""
    return tuple(sorted(abstract_concepts(label)))
