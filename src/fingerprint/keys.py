"""DNA-native MULTI fingerprints: D0+D1 landmark pairs on typed directed paths."""

from __future__ import annotations

import hashlib
from collections import defaultdict, deque
from typing import Literal

from src.graph import ThoughtGraph

FEATURE_VERSION = "resonance-fingerprint/0.1-multi"
MAX_PATH_LENGTH = 3
DescriptorVariant = Literal["D0", "D1", "MULTI"]
VARIANTS: tuple[DescriptorVariant, ...] = ("D0", "D1", "MULTI")


def _h64(*parts: object) -> str:
    return hashlib.blake2b("|".join(map(str, parts)).encode("utf-8"), digest_size=8).hexdigest()


def _adjacency(graph: ThoughtGraph) -> dict[str, list[tuple[str, str, str, str]]]:
    """Undirected traversal view: (neighbor, relation_type, assertion, direction)."""
    adj: dict[str, list[tuple[str, str, str, str]]] = defaultdict(list)
    for rel in graph.relations:
        adj[rel.source].append((rel.target, rel.type, rel.assertion, "+"))
        adj[rel.target].append((rel.source, rel.type, rel.assertion, "-"))
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
            for neighbor, rel_type, assertion, direction in adj[node.id]
            if neighbor in base
        )
        out[node.id] = _h64("wl", base[node.id], *neighborhood)
    return out


def path_signature(graph: ThoughtGraph, start: str, end: str) -> tuple[tuple[tuple[str, str, str], ...], int] | None:
    adj = _adjacency(graph)
    prev: dict[str, tuple[str, str, str, str] | None] = {start: None}
    frontier = deque([start])
    depth = {start: 0}
    while frontier:
        node = frontier.popleft()
        if depth[node] >= MAX_PATH_LENGTH:
            continue
        for neighbor, rel_type, assertion, direction in adj[node]:
            if neighbor in prev:
                continue
            prev[neighbor] = (node, rel_type, assertion, direction)
            depth[neighbor] = depth[node] + 1
            if neighbor == end:
                frontier.clear()
                break
            frontier.append(neighbor)
    if end not in prev or prev[end] is None:
        return None
    tokens: list[tuple[str, str, str]] = []
    current = end
    while current != start:
        parent, rel_type, assertion, direction = prev[current]  # type: ignore[misc]
        tokens.append((direction, rel_type, assertion))
        current = parent
    tokens.reverse()
    return tuple(tokens), len(tokens)


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
