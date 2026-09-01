"""DNA-native MULTI fingerprints: D0+D1 landmark pairs on typed directed paths."""

from __future__ import annotations

import hashlib
from collections import defaultdict, deque
from typing import Literal

from src.graph import ThoughtGraph

FEATURE_VERSION = "resonance-fingerprint/0.1.1-multi"
MAX_PATH_LENGTH = 3
DescriptorVariant = Literal["D0", "D1", "MULTI"]
VARIANTS: tuple[DescriptorVariant, ...] = ("D0", "D1", "MULTI")


def _h64(*parts: object) -> str:
    return hashlib.blake2b("|".join(map(str, parts)).encode("utf-8"), digest_size=8).hexdigest()


def _adjacency(graph: ThoughtGraph) -> dict[str, list[tuple[str, str, str, str, str]]]:
    """Undirected traversal view independent of relation-ID insertion order.

    Each entry is (neighbor, relation_type, assertion, direction, neighbor_role).
    Neighbor lists are sorted by semantic fields only; relation IDs never enter
    the key. Equal-length paths are canonicalized in ``path_signature``.
    """
    roles = {node.id: node.role for node in graph.nodes}
    adj: dict[str, list[tuple[str, str, str, str, str]]] = defaultdict(list)
    for rel in graph.relations:
        adj[rel.source].append((rel.target, rel.type, rel.assertion, "+", roles.get(rel.target, "")))
        adj[rel.target].append((rel.source, rel.type, rel.assertion, "-", roles.get(rel.source, "")))
    for node_id, entries in adj.items():
        adj[node_id] = sorted(entries, key=lambda item: (item[3], item[1], item[2], item[4], item[0]))
    return adj


def d0(graph: ThoughtGraph) -> dict[str, str]:
    return {node.id: node.role for node in graph.nodes}


def d1(graph: ThoughtGraph) -> dict[str, str]:
    base = d0(graph)
    adj = _adjacency(graph)
    out: dict[str, str] = {}
    for node in graph.nodes:
        neighborhood = sorted(
            (direction, rel_type, assertion, base[neighbor])
            for neighbor, rel_type, assertion, direction, _role in adj[node.id]
            if neighbor in base
        )
        out[node.id] = _h64("wl", base[node.id], *neighborhood)
    return out


def path_signature(graph: ThoughtGraph, start: str, end: str) -> tuple[tuple[tuple[str, str, str], ...], int] | None:
    """Shortest typed/directed path, canonical among equal-length alternatives.

    All shortest paths of length <= MAX_PATH_LENGTH are enumerated. The
    lexicographically smallest token sequence of ``(direction, type, assertion)``
    is kept, so renaming relation IDs cannot change the MULTI key.
    """
    adj = _adjacency(graph)
    depth = {start: 0}
    parents: dict[str, list[tuple[str, str, str, str]]] = {start: []}
    frontier = deque([start])
    found_depth: int | None = None
    while frontier:
        node = frontier.popleft()
        if found_depth is not None and depth[node] >= found_depth:
            continue
        if depth[node] >= MAX_PATH_LENGTH:
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


def _scales(graph: ThoughtGraph, variant: DescriptorVariant) -> list[tuple[str, dict[str, str]]]:
    if variant == "D0":
        return [("s0", d0(graph))]
    if variant == "D1":
        return [("s1", d1(graph))]
    return [("s0", d0(graph)), ("s1", d1(graph))]


def fingerprints(graph: ThoughtGraph, variant: DescriptorVariant = "MULTI") -> list[tuple[str, str, str]]:
    """Return (key, endpoint_a, endpoint_b) records. Labels never enter the key."""
    if variant not in VARIANTS:
        raise ValueError(f"unsupported fingerprint variant: {variant}")
    adj = _adjacency(graph)
    landmarks = [node.id for node in graph.nodes if adj[node.id]]
    records: list[tuple[str, str, str]] = []
    for tag, desc in _scales(graph, variant):
        for left in landmarks:
            for right in landmarks:
                if left == right:
                    continue
                path = path_signature(graph, left, right)
                if path is None:
                    continue
                signature, distance = path
                key = _h64(tag, desc[left], desc[right], signature, f"d{distance}")
                records.append((key, left, right))
    return records


def keyset(graph: ThoughtGraph, variant: DescriptorVariant = "MULTI") -> set[str]:
    return {key for key, _, _ in fingerprints(graph, variant)}
