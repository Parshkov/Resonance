"""DNA-native fingerprints: label-free structural keys plus concept keys.

Two key families, both deterministic and computed without any model:

* **structural** (``fingerprints``): D0 (role) and D1 (one-round WL over roles
  and typed relations) landmark pairs joined by the canonical shortest typed
  path (<= 3). Labels never enter these keys, so they are invariant to
  vocabulary and domain -- and, by the same token, blind to content. They
  retrieve "same skeleton" candidates.

* **concept** (``concept_fingerprints``): the same landmark-pair construction,
  but the descriptor is (role, abstract concept classes of the label) from the
  deterministic lexicon. "heat accumulation" and "backlog pileup" share the
  ACCUMULATION class, so an analogy in another domain still shares these
  keys, while a template coincidence with concept-free labels does not.
  Single-landmark concept keys are also emitted so small or partial graphs
  keep retrievable evidence.

The index weights every key by corpus IDF; nothing is hard-dropped below a
stop-key threshold, so generic motifs are *down-weighted* rather than made
unretrievable (the v0.1 dead-key defect).
"""

from __future__ import annotations

import hashlib
from collections import defaultdict, deque
from typing import Literal

from src.graph import ThoughtGraph
from src.semantics import SEMANTICS_VERSION, abstract_signature
from src.semantics.lexicon import RELATED

FEATURE_VERSION = "resonance-fingerprint/0.2.0-multi+concept;" + SEMANTICS_VERSION
MAX_PATH_LENGTH = 3
CONCEPT_MAX_PATH_LENGTH = 2
DescriptorVariant = Literal["D0", "D1", "MULTI"]
VARIANTS: tuple[DescriptorVariant, ...] = ("D0", "D1", "MULTI")

Adjacency = dict[str, list[tuple[str, str, str, str, str]]]


def _h64(*parts: object) -> str:
    return hashlib.blake2b("|".join(map(str, parts)).encode("utf-8"), digest_size=8).hexdigest()


def _adjacency(graph: ThoughtGraph) -> Adjacency:
    """Undirected traversal view independent of relation-ID insertion order.

    Each entry is (neighbor, relation_type, assertion, direction, neighbor_role).
    Neighbor lists are sorted by semantic fields only; relation IDs never enter
    the key. Equal-length paths are canonicalized in ``path_signature``.
    """
    roles = {node.id: node.role for node in graph.nodes}
    adj: Adjacency = defaultdict(list)
    for rel in graph.relations:
        adj[rel.source].append((rel.target, rel.type, rel.assertion, "+", roles.get(rel.target, "")))
        adj[rel.target].append((rel.source, rel.type, rel.assertion, "-", roles.get(rel.source, "")))
    for node_id, entries in adj.items():
        adj[node_id] = sorted(entries, key=lambda item: (item[3], item[1], item[2], item[4], item[0]))
    return adj


def d0(graph: ThoughtGraph) -> dict[str, str]:
    return {node.id: node.role for node in graph.nodes}


def d1(graph: ThoughtGraph, adj: Adjacency | None = None) -> dict[str, str]:
    base = d0(graph)
    adj = adj if adj is not None else _adjacency(graph)
    out: dict[str, str] = {}
    for node in graph.nodes:
        neighborhood = sorted(
            (direction, rel_type, assertion, base[neighbor])
            for neighbor, rel_type, assertion, direction, _role in adj[node.id]
            if neighbor in base
        )
        out[node.id] = _h64("wl", base[node.id], *neighborhood)
    return out


MAX_CONCEPTS_PER_NODE = 3
EXPANSION_MIN_RELATEDNESS = 0.6


def _related_classes(concept: str) -> list[str]:
    out = []
    for pair, w in RELATED.items():
        if concept in pair and w >= EXPANSION_MIN_RELATEDNESS:
            (other,) = tuple(pair - {concept}) or (concept,)
            out.append(other)
    return sorted(out)


def concept_descriptor(graph: ThoughtGraph, *, expand: bool = False) -> dict[str, tuple[str, ...]]:
    """Per node: up to MAX_CONCEPTS_PER_NODE "role:CLASS" descriptors; empty when the lexicon is silent.

    Keys are emitted per class (not per class *set*) so that two labels sharing
    one abstract notion still share a key even when their other classes differ.
    ``expand`` (query side only) adds strongly related classes so that an
    analogy realised by a neighbouring notion (COOLING vs DAMPING) is reachable.
    """
    out: dict[str, tuple[str, ...]] = {}
    for node in graph.nodes:
        sig = list(abstract_signature(node.label)[:MAX_CONCEPTS_PER_NODE])
        if expand:
            for c in list(sig):
                for r in _related_classes(c):
                    if r not in sig:
                        sig.append(r)
        out[node.id] = tuple(node.role + ":" + c for c in sig)
    return out


def path_signature(
    graph: ThoughtGraph,
    start: str,
    end: str,
    *,
    adj: Adjacency | None = None,
    max_length: int = MAX_PATH_LENGTH,
) -> tuple[tuple[tuple[str, str, str], ...], int] | None:
    """Shortest typed/directed path, canonical among equal-length alternatives.

    All shortest paths of length <= ``max_length`` are enumerated. The
    lexicographically smallest token sequence of ``(direction, type, assertion)``
    is kept, so renaming relation IDs cannot change the key.
    """
    adj = adj if adj is not None else _adjacency(graph)
    depth = {start: 0}
    parents: dict[str, list[tuple[str, str, str, str]]] = {start: []}
    frontier = deque([start])
    found_depth: int | None = None
    while frontier:
        node = frontier.popleft()
        if found_depth is not None and depth[node] >= found_depth:
            continue
        if depth[node] >= max_length:
            continue
        for neighbor, rel_type, assertion, direction, _role in adj[node]:
            nxt = depth[node] + 1
            if neighbor not in depth:
                depth[neighbor] = nxt
                parents[neighbor] = [(node, direction, rel_type, assertion)]
                if neighbor == end:
                    found_depth = nxt
                elif found_depth is None:
                    frontier.append(neighbor)
            elif depth[neighbor] == nxt:
                parents[neighbor].append((node, direction, rel_type, assertion))
    if end not in depth or end == start:
        return None

    def _paths(node: str) -> list[tuple[tuple[str, str, str], ...]]:
        if node == start:
            return [()]
        out: list[tuple[tuple[str, str, str], ...]] = []
        for parent, direction, rel_type, assertion in parents[node]:
            for prefix in _paths(parent):
                out.append(prefix + ((direction, rel_type, assertion),))
        return out

    signatures = _paths(end)
    if not signatures:
        return None
    best = min(signatures)
    return best, len(best)


def _scales(graph: ThoughtGraph, variant: DescriptorVariant, adj: Adjacency) -> list[tuple[str, dict[str, str]]]:
    if variant == "D0":
        return [("s0", d0(graph))]
    if variant == "D1":
        return [("s1", d1(graph, adj))]
    return [("s0", d0(graph)), ("s1", d1(graph, adj))]


def _pair_keys(
    graph: ThoughtGraph,
    adj: Adjacency,
    scales: list[tuple[str, dict[str, str]]],
    *,
    max_length: int,
) -> list[tuple[str, str, str]]:
    landmarks = [node.id for node in graph.nodes if adj[node.id]]
    records: list[tuple[str, str, str]] = []
    paths: dict[tuple[str, str], tuple | None] = {}
    for left in landmarks:
        for right in landmarks:
            if left == right:
                continue
            paths[(left, right)] = path_signature(graph, left, right, adj=adj, max_length=max_length)
    for tag, desc in scales:
        for (left, right), path in paths.items():
            if path is None:
                continue
            signature, distance = path
            key = _h64(tag, desc[left], desc[right], signature, f"d{distance}")
            records.append((key, left, right))
    return records


def fingerprints(graph: ThoughtGraph, variant: DescriptorVariant = "MULTI") -> list[tuple[str, str, str]]:
    """Label-free structural (key, endpoint_a, endpoint_b) records."""
    if variant not in VARIANTS:
        raise ValueError(f"unsupported fingerprint variant: {variant}")
    adj = _adjacency(graph)
    return _pair_keys(graph, adj, _scales(graph, variant, adj), max_length=MAX_PATH_LENGTH)


def concept_fingerprints(graph: ThoughtGraph, *, expand: bool = False) -> list[tuple[str, str, str]]:
    """Concept-aware (key, endpoint_a, endpoint_b) records.

    Pair keys: one per (class_left, class_right, typed path <= 2). Node keys
    (endpoint_b == endpoint_a): one per (role, class), so partial and very
    small graphs still carry retrievable content evidence.
    """
    adj = _adjacency(graph)
    desc = concept_descriptor(graph, expand=expand)
    records: list[tuple[str, str, str]] = []
    landmarks = [node.id for node in graph.nodes if adj[node.id] and desc[node.id]]
    for left in landmarks:
        for right in landmarks:
            if left == right:
                continue
            path = path_signature(graph, left, right, adj=adj, max_length=CONCEPT_MAX_PATH_LENGTH)
            if path is None:
                continue
            signature, distance = path
            for dl in desc[left]:
                for dr in desc[right]:
                    records.append((_h64("c0", dl, dr, signature, f"d{distance}"), left, right))
    for node in graph.nodes:
        for d in desc[node.id]:
            records.append((_h64("c1", d), node.id, node.id))
    return records


def keyset(graph: ThoughtGraph, variant: DescriptorVariant = "MULTI") -> set[str]:
    return {key for key, _, _ in fingerprints(graph, variant)}


def concept_keyset(graph: ThoughtGraph) -> set[str]:
    return {key for key, _, _ in concept_fingerprints(graph)}
