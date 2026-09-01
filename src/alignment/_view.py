"""Typed directed view of a ThoughtGraph for alignment.

Structure is kept per relation type, direction preserved, exactly as
ADR-0003 requires: a single scalar/symmetrized structure matrix is prohibited
as the primary encoding.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Mapping

from src.graph import ThoughtGraph

# Deterministic ordering of the closed relation vocabulary (thought-dna/0.1).
RELATION_TYPES: tuple[str, ...] = (
    "causes", "prevents", "requires", "part_of", "constrains", "supports", "contradicts",
)

# Polarity classes for the hard sign boundary: causes/prevents on the same
# mapped endpoints is a sign conflict, not merely a type mismatch.
SIGN_OPPOSITES = {("causes", "prevents"), ("prevents", "causes")}


def _tokens(label: str) -> frozenset[str]:
    return frozenset(t for t in "".join(c.lower() if c.isalnum() else " " for c in label).split() if t)


class GraphView:
    def __init__(self, graph: ThoughtGraph):
        self.graph = graph
        self.nodes = list(graph.nodes)
        self.n = len(self.nodes)
        self.index = {node.id: i for i, node in enumerate(self.nodes)}
        self.relations = list(graph.relations)
        self.rel_by_id = {rel.id: rel for rel in self.relations}
        # channels[type] = list of (src_idx, tgt_idx, confidence, relation)
        self.channels: dict[str, list[tuple[int, int, float, object]]] = defaultdict(list)
        # rels_between[(src_idx, tgt_idx)] = [relation, ...] (any type, directed)
        self.rels_between: dict[tuple[int, int], list[object]] = defaultdict(list)
        # adjacency for path search: adj[src_idx] = [(tgt_idx, relation)]
        self.adj: dict[int, list[tuple[int, object]]] = defaultdict(list)
        for rel in self.relations:
            i, j = self.index[rel.source], self.index[rel.target]
            self.channels[rel.type].append((i, j, rel.extract_conf, rel))
            self.rels_between[(i, j)].append(rel)
            self.adj[i].append((j, rel))
        self._token_cache = [_tokens(node.label) for node in self.nodes]
        self._about = [frozenset(ref.id for ref in (node.knowledge.about if node.knowledge else ()))
                      for node in self.nodes]
        self._requires = [frozenset(ref.id for ref in (node.knowledge.requires if node.knowledge else ()))
                         for node in self.nodes]

    def about_ids(self) -> frozenset[str]:
        out: set[str] = set()
        for s in self._about:
            out |= s
        return frozenset(out)

    def requires_ids(self) -> frozenset[str]:
        out: set[str] = set()
        for s in self._requires:
            out |= s
        return frozenset(out)


def node_affinity(a: GraphView, b: GraphView, weights: Mapping[str, float]) -> list[list[float]]:
    """DNA-native deterministic node affinity in [0,1]; no embeddings, no LLM.

    Role compatibility carries cross-domain analogy; label/knowledge overlap
    carries same-domain support. Structure dominates via alpha anyway.
    """
    w_role, w_label, w_know = weights["role"], weights["label"], weights["knowledge"]
    out = [[0.0] * b.n for _ in range(a.n)]
    for i in range(a.n):
        na = a.nodes[i]
        ta = a._token_cache[i]
        ka = a._about[i] | a._requires[i]
        for j in range(b.n):
            nb = b.nodes[j]
            role = 1.0 if na.role == nb.role else 0.0
            if ta or b._token_cache[j]:
                inter = len(ta & b._token_cache[j])
                union = len(ta | b._token_cache[j])
                label = inter / union if union else 0.0
            else:
                label = 0.0
            kb = b._about[j] | b._requires[j]
            if ka or kb:
                know = len(ka & kb) / len(ka | kb) if (ka | kb) else 0.0
            else:
                know = 0.0
            conf = min(na.extract_conf, nb.extract_conf)
            out[i][j] = conf * (w_role * role + w_label * label + w_know * know)
    return out
