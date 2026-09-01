"""Guarded edge-to-path matching for transparent granularity (ADR-0003 / R0-D).

A canonical query relation may match a bounded candidate path (<= 4 relations)
only when every guard passes. Unknown relation composition, meaningful
intermediates, polarity, assertion, direction, or modality differences reject
the match. v0.1 licenses only uniform `causes` composition (causes o causes ->
causes); every other composition is unknown and rejected.

Engine-side meaningfulness guard: every interior node must be atomic=false and
must lie on the path with no other role in the mapping. Benchmark v0.2's
V02-04 demonstrates that gold may still declare such an interior meaningful;
that residual risk is why path matching is config-gated (guarded/off) and why
the OFF configuration is measured too.
"""

from __future__ import annotations

from .scoring_types import PathMatch  # re-exported dataclass
from ._view import GraphView

LICENSED_COMPOSITION = {"causes"}
MAX_PATH_RELATIONS = 4


def guarded_path_matches(
    va: GraphView,
    vb: GraphView,
    mapping_pairs: list[tuple[int, int]],
    preserved_query_rel_ids: set[str],
) -> list[PathMatch]:
    mapping = dict(mapping_pairs)
    mapped_c = set(mapping.values())
    out: list[PathMatch] = []
    used_c_rels: set[str] = set()
    for (i, j), rels in sorted(va.rels_between.items()):
        if i not in mapping or j not in mapping:
            continue
        for rel in rels:
            if rel.id in preserved_query_rel_ids:
                continue
            if rel.type not in LICENSED_COMPOSITION:
                continue
            if rel.assertion != "asserted" or rel.modality != "actual":
                continue
            path = _find_path(vb, mapping[i], mapping[j], rel, mapped_c, used_c_rels)
            if path is None:
                continue
            rel_ids, interior = path
            used_c_rels.update(rel_ids)
            out.append(PathMatch(
                query_relation=rel.id,
                candidate_relations=tuple(rel_ids),
                realizes_nodes=tuple(vb.nodes[k].id for k in interior),
                support=rel.extract_conf,
            ))
    return out


def _find_path(vb: GraphView, start: int, goal: int, q_rel, mapped_c: set[int],
               used: set[str]):
    """Deterministic bounded DFS for a licensed directed path start -> goal."""
    best: list[tuple[list[str], list[int]]] = []

    def dfs(node: int, rel_ids: list[str], interior: list[int]):
        if len(rel_ids) > MAX_PATH_RELATIONS:
            return
        if node == goal and len(rel_ids) >= 2:
            best.append((rel_ids[:], interior[:]))
            return
        if node == goal:
            return
        for (nxt, rel) in sorted(vb.adj.get(node, []), key=lambda x: x[1].id):
            if rel.id in used or rel.id in rel_ids:
                continue
            if rel.type != q_rel.type:                 # uniform composition only
                return_ = True
                continue
            if rel.assertion != q_rel.assertion or rel.modality != q_rel.modality:
                continue
            if nxt != goal:
                interior_node = vb.nodes[nxt]
                if interior_node.atomic:               # meaningful guard
                    continue
                if nxt in mapped_c:                    # interior already mapped
                    continue
                if interior_node.assertion != "asserted" or interior_node.modality != "actual":
                    continue                           # modal/negated mediator
                if interior_node.role != "mechanism":
                    continue                           # constraint/evidence/outcome
                                                       # mediators carry meaning
                # transparency requires a pure degree-1 interior: any edge
                # beyond the two path edges (branch, merge, constraint,
                # evidence attachment) makes the mediator non-transparent
                # (R0-D guards; benchmark v0.2 families 06-09).
                incident = sum(1 for (_u, _v2), rels2 in vb.rels_between.items()
                               for _r in rels2 if _u == nxt or _v2 == nxt)
                if incident != 2:
                    continue
            dfs(nxt, rel_ids + [rel.id], interior + ([nxt] if nxt != goal else []))

    dfs(start, [], [])
    if not best:
        return None
    best.sort(key=lambda x: (len(x[0]), x[0]))
    return best[0]
