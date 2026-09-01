"""Transport-shape serialization of accepted engine results.

Shape-only: every number/mapping comes from the frozen interfaces
(ScoreVector.to_wire, Explanation, provenance items); nothing is computed
here (engineering contract section 7).
"""

from __future__ import annotations

from typing import Any

from src.graph import ThoughtGraph
from src.interfaces import (
    ConfigRef,
    Contradiction,
    EdgePathMatch,
    Explanation,
    ItemProvenance,
    NodeMatch,
    RelationMatch,
    ResonanceHit,
    VerifierResult,
)


def _config_ref(c: ConfigRef) -> dict[str, str]:
    return {"component": c.component,
            "component_version": c.component_version,
            "config_hash": c.config_hash,
            "schema_version": c.schema_version}


def _prov(p: ItemProvenance) -> dict[str, Any]:
    return {"thought_id": p.thought_id, "item_id": p.item_id,
            "provenance_kind": p.provenance_kind,
            "spans": [{"start": s.start, "end": s.end, "text": s.text} for s in p.spans]}


def _node_match(m: NodeMatch) -> dict[str, Any]:
    return {"query_node": m.query_node, "candidate_node": m.candidate_node,
            "support": m.support, "query_provenance": _prov(m.query_provenance),
            "candidate_provenance": _prov(m.candidate_provenance)}


def _rel_match(m: RelationMatch) -> dict[str, Any]:
    return {"query_relation": m.query_relation, "candidate_relation": m.candidate_relation,
            "support": m.support, "query_provenance": _prov(m.query_provenance),
            "candidate_provenance": _prov(m.candidate_provenance)}


def _path_match(m: EdgePathMatch) -> dict[str, Any]:
    return {"query_relation": m.query_relation,
            "candidate_relations": list(m.candidate_relations),
            "realizes_nodes": list(m.realizes_nodes), "support": m.support,
            "query_provenance": _prov(m.query_provenance),
            "candidate_provenances": [_prov(p) for p in m.candidate_provenances],
            "realizes_node_provenances": [_prov(p) for p in m.realizes_node_provenances]}


def _contradiction(c: Contradiction) -> dict[str, Any]:
    return {"kind": c.kind, "query_item": c.query_item, "candidate_item": c.candidate_item,
            "contribution": c.contribution, "rule_version": c.rule_version,
            "query_provenance": _prov(c.query_provenance),
            "candidate_provenance": _prov(c.candidate_provenance)}


def _explanation(e: Explanation) -> dict[str, Any]:
    return {"mapping": [_node_match(m) for m in e.mapping],
            "matched_relations": [_rel_match(m) for m in e.matched_relations],
            "edge_path_matches": [_path_match(m) for m in e.edge_path_matches],
            "unmatched_query_nodes": list(e.unmatched_query_nodes),
            "unmatched_candidate_nodes": list(e.unmatched_candidate_nodes),
            "unmatched_query_relations": list(e.unmatched_query_relations),
            "unmatched_candidate_relations": list(e.unmatched_candidate_relations),
            "contradictions": [_contradiction(c) for c in e.contradictions],
            "retrieval_channels": list(e.retrieval_channels),
            "systematicity_systems": [list(s) for s in e.systematicity_systems],
            "score_model_version": e.score_model_version,
            "schema_version": e.schema_version, "config_hash": e.config_hash}


def verifier_result(r: VerifierResult) -> dict[str, Any]:
    return {"contract_version": r.contract_version, "query_id": r.query_id,
            "candidate_id": r.candidate_id, "candidate_config": r.candidate_config,
            "classification": r.classification, "confidence": r.confidence,
            "hard_rejection": r.hard_rejection,
            "components": r.components.to_wire(),
            "retrieval_flags": r.retrieval_flags.to_wire(),
            "mapping": [_node_match(m) for m in r.mapping],
            "matched_relations": [_rel_match(m) for m in r.matched_relations],
            "edge_path_matches": [_path_match(m) for m in r.edge_path_matches],
            "unmatched_query_nodes": list(r.unmatched_query_nodes),
            "unmatched_candidate_nodes": list(r.unmatched_candidate_nodes),
            "unmatched_query_relations": list(r.unmatched_query_relations),
            "unmatched_candidate_relations": list(r.unmatched_candidate_relations),
            "contradictions": [_contradiction(c) for c in r.contradictions],
            "explanation": _explanation(r.explanation),
            "solver_config": _config_ref(r.solver_config)}


def resonance_hit(h: ResonanceHit) -> dict[str, Any]:
    c = h.candidate
    return {"candidate": {"candidate_id": c.candidate_id,
                          "channel_scores": dict(c.channel_scores),
                          "channel_ranks": dict(c.channel_ranks),
                          "seed_correspondences": [
                              {"query_node": s.query_node, "candidate_node": s.candidate_node,
                               "support": s.support, "channel": s.channel}
                              for s in c.seed_correspondences],
                          "usable_query_evidence": c.usable_query_evidence,
                          "requires_structural_verification": c.requires_structural_verification,
                          "polarity_reliable": c.polarity_reliable,
                          "index_version": c.index_version,
                          "feature_version": c.feature_version,
                          "corpus_snapshot": c.corpus_snapshot,
                          "config": _config_ref(c.config)},
            "verification": verifier_result(h.verification)}


def thought(g: ThoughtGraph) -> dict[str, Any]:
    return g.to_dict()
