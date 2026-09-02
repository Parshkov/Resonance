"""Deterministic collision probe for R0-H-REPEAT-H7Q2.

This is not a benchmark of the accepted Resonance engine. It is a deliberately
small red-team probe of a tempting Shazam-like design choice: making local
relational fingerprints increasingly domain-invariant by stripping node
semantics/roles.

Expected output with Python 3.11+:
relation-sequence-only: query_features=7 mean=0.593 p95=0.875 p99=0.875 max=1.000
typed-two-hop-path: query_features=15 mean=0.012 p95=0.059 p99=0.095 max=0.200
"""

from __future__ import annotations

import collections
import random
import statistics

SEED = 42
N_GRAPHS = 5000
N_NODES = 25
EDGE_PROB = 0.08
NODE_ROLES = ("problem", "mechanism", "outcome", "constraint")
RELATIONS = ("causes", "enables", "inhibits")


def generate_graph(rng: random.Random):
    roles = [rng.choice(NODE_ROLES) for _ in range(N_NODES)]
    edges = []
    for src in range(N_NODES):
        for dst in range(src + 1, N_NODES):
            if rng.random() < EDGE_PROB:
                edges.append((src, dst, rng.choice(RELATIONS)))
    return roles, edges


def relation_sequence_fingerprints(graph):
    _roles, edges = graph
    outgoing = collections.defaultdict(list)
    for src, dst, relation in edges:
        outgoing[src].append((dst, relation))

    fingerprints = set()
    for _src, first_hops in outgoing.items():
        for middle, relation_1 in first_hops:
            for _dst, relation_2 in outgoing.get(middle, ()):
                fingerprints.add((relation_1, relation_2))
    return fingerprints


def typed_path_fingerprints(graph):
    roles, edges = graph
    outgoing = collections.defaultdict(list)
    for src, dst, relation in edges:
        outgoing[src].append((dst, relation))

    fingerprints = set()
    for src, first_hops in outgoing.items():
        for middle, relation_1 in first_hops:
            for dst, relation_2 in outgoing.get(middle, ()):
                fingerprints.add(
                    (roles[src], relation_1, roles[middle], relation_2, roles[dst])
                )
    return fingerprints


def jaccard(left, right):
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


def summarize(name, fingerprints):
    query = fingerprints[0]
    scores = [jaccard(query, candidate) for candidate in fingerprints[1:]]
    ordered = sorted(scores)
    p95 = ordered[int(0.95 * (len(ordered) - 1))]
    p99 = ordered[int(0.99 * (len(ordered) - 1))]
    print(
        f"{name}: query_features={len(query)} "
        f"mean={statistics.mean(scores):.3f} "
        f"p95={p95:.3f} p99={p99:.3f} max={max(scores):.3f}"
    )


def main():
    rng = random.Random(SEED)
    graphs = [generate_graph(rng) for _ in range(N_GRAPHS)]
    summarize(
        "relation-sequence-only",
        [relation_sequence_fingerprints(graph) for graph in graphs],
    )
    summarize(
        "typed-two-hop-path",
        [typed_path_fingerprints(graph) for graph in graphs],
    )


if __name__ == "__main__":
    main()
