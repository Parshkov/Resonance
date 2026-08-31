"""Cheap red-team falsifiers for Resonance's v0.1 structural channel.

This is not an implementation of the future R3/R4 engine.  It deliberately
copies only the already-published E1 retrieval primitives: D0 role landmarks,
one-round directed typed D1 labels, shortest typed paths of length <= 3,
document-frequency stopping, and exact key-set comparison.  Keys remain Python
tuples so cryptographic hash collisions cannot explain the results.

Run:
    python3 research/experiments/R0_H_repeat_falsifier.py

Dependencies: Python standard library only.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict, deque
from dataclasses import dataclass


ROLES = (
    "problem",
    "mechanism",
    "state",
    "outcome",
    "constraint",
    "method",
    "evidence",
    "resource",
    "agent",
)
RELATIONS = (
    "causes",
    "prevents",
    "requires",
    "part_of",
    "constrains",
    "supports",
    "contradicts",
)


@dataclass(frozen=True)
class Graph:
    roles: tuple[str, ...]
    edges: tuple[tuple[int, int, str], ...]

    def adjacency(self) -> dict[int, list[tuple[int, str, str]]]:
        result: dict[int, list[tuple[int, str, str]]] = defaultdict(list)
        for source, target, relation in self.edges:
            result[source].append((target, relation, "+"))
            result[target].append((source, relation, "-"))
        for node in result:
            result[node].sort()
        return result


def digest(value: object) -> str:
    return hashlib.sha256(repr(value).encode("utf-8")).hexdigest()[:16]


def descriptors(graph: Graph, scale: str) -> dict[int, object]:
    if scale == "D0":
        return dict(enumerate(graph.roles))
    if scale != "D1":
        raise ValueError(scale)
    adjacency = graph.adjacency()
    return {
        node: (
            graph.roles[node],
            tuple(sorted((direction, relation, graph.roles[other]) for other, relation, direction in adjacency[node])),
        )
        for node in range(len(graph.roles))
    }


def shortest_path_signature(graph: Graph, start: int, end: int, max_length: int = 3) -> tuple[tuple[str, str], ...] | None:
    adjacency = graph.adjacency()
    queue = deque([(start, ())])
    visited = {start}
    while queue:
        node, signature = queue.popleft()
        if len(signature) >= max_length:
            continue
        for other, relation, direction in adjacency[node]:
            if other in visited:
                continue
            next_signature = signature + ((direction, relation),)
            if other == end:
                return next_signature
            visited.add(other)
            queue.append((other, next_signature))
    return None


def fingerprints(graph: Graph, variant: str) -> frozenset[tuple[object, ...]]:
    scales = {"D0": ("D0",), "D1": ("D1",), "MULTI": ("D0", "D1")}[variant]
    active = tuple(sorted(graph.adjacency()))
    result: set[tuple[object, ...]] = set()
    for scale in scales:
        desc = descriptors(graph, scale)
        for start in active:
            for end in active:
                if start == end:
                    continue
                path = shortest_path_signature(graph, start, end)
                if path is not None:
                    result.add((scale, desc[start], desc[end], path, len(path)))
    return frozenset(result)


def jaccard(left: frozenset[object], right: frozenset[object]) -> float:
    return len(left & right) / len(left | right) if left | right else 0.0


def random_graph(rng: random.Random) -> Graph:
    count = rng.randint(6, 10)
    roles = tuple(rng.choice(ROLES) for _ in range(count))
    edges = [(rng.randrange(node), node, rng.choice(RELATIONS)) for node in range(1, count)]
    return Graph(roles, tuple(edges))


def df_stop_attack() -> dict[str, object]:
    # Fifty domain-disjoint candidates share exactly the same four-node causal
    # skeleton.  Only one is contextually intended; that fact is absent from
    # the structural representation.  It is deliberately placed after top-20.
    motif = Graph(
        ("resource", "mechanism", "state", "outcome"),
        ((0, 1, "causes"), (1, 2, "causes"), (2, 3, "causes")),
    )
    rng = random.Random(20260831)
    corpus = [motif for _ in range(50)] + [random_graph(rng) for _ in range(950)]
    positive_index = 49
    result: dict[str, object] = {
        "corpus_size": len(corpus),
        "identical_motif_candidates": 50,
        "contextual_positive_index_zero_based": positive_index,
    }
    for variant in ("D0", "D1", "MULTI"):
        query_keys = fingerprints(motif, variant)
        document_frequency: Counter[tuple[object, ...]] = Counter()
        for graph in corpus:
            document_frequency.update(fingerprints(graph, variant))
        cutoff = max(5, 0.005 * len(corpus))
        live = frozenset(key for key in query_keys if document_frequency[key] <= cutoff)
        # All identical candidates tie before stopping; stable corpus order is
        # the only ranking information.  After stopping there is no score.
        result[variant] = {
            "query_keys": len(query_keys),
            "live_query_keys": len(live),
            "minimum_query_key_df": min(document_frequency[key] for key in query_keys),
            "df_cutoff": cutoff,
            "positive_in_arbitrary_top20_without_stopping": positive_index < 20,
            "retrievable_after_stopping": bool(live),
        }
    return result


def edit_survival_attack() -> dict[str, object]:
    base = Graph(
        ("resource", "mechanism", "state", "outcome", "constraint", "method", "resource", "state"),
        (
            (0, 1, "causes"),
            (1, 2, "causes"),
            (2, 3, "causes"),
            (4, 1, "constrains"),
            (5, 1, "prevents"),
            (3, 6, "requires"),
            (7, 2, "supports"),
        ),
    )
    relation_error = Graph(base.roles, tuple((u, v, "prevents" if (u, v, r) == (1, 2, "causes") else r) for u, v, r in base.edges))
    irrelevant_branch = Graph(base.roles + ("state",), base.edges + ((3, 8, "causes"),))
    missing_relation = Graph(base.roles, tuple(edge for edge in base.edges if edge != (7, 2, "supports")))
    transforms = {
        "one_relation_type_error": relation_error,
        "one_irrelevant_branch": irrelevant_branch,
        "one_missing_relation": missing_relation,
    }
    result: dict[str, object] = {}
    for variant in ("D0", "D1", "MULTI"):
        original = fingerprints(base, variant)
        result[variant] = {
            name: round(jaccard(original, fingerprints(graph, variant)), 4)
            for name, graph in transforms.items()
        }
    return result


def representation_collision() -> dict[str, object]:
    # Reading A: the audit supports the proposition "overload causes failure".
    # Reading B: the audit supports the overload state; overload causes failure.
    # Thought DNA v0.1 cannot use a relation/proposition as an endpoint.  A
    # flattening writer emits this same graph for both readings; an abstaining
    # writer must drop A's higher-order support and lose the intended evidence.
    flattened = Graph(
        ("evidence", "state", "outcome"),
        ((0, 1, "supports"), (1, 2, "causes")),
    )
    return {
        "reading_a": "audit supports [overload causes failure]",
        "reading_b": "audit supports overload; overload causes failure",
        "flattened_signature": digest((flattened.roles, flattened.edges)),
        "D0_signature": digest(sorted(fingerprints(flattened, "D0"), key=repr)),
        "D1_signature": digest(sorted(fingerprints(flattened, "D1"), key=repr)),
        "distinguishable_after_flattening": False,
    }


if __name__ == "__main__":
    print(json.dumps({
        "experiment": "R0-H-REPEAT-S7D3 cheap falsifiers",
        "seed": 20260831,
        "df_stop_attack": df_stop_attack(),
        "edit_survival_attack": edit_survival_attack(),
        "representation_collision": representation_collision(),
    }, indent=2, sort_keys=True))
