"""R4 structural verifier: proposal -> consistency -> round -> adjudicate.

Implements `src.interfaces.StructuralVerifier`. The pipeline and its hard
rules follow ADR-0003; component formulas follow RESONANCE_SCORING_v0.1.
"""

from __future__ import annotations

import json
import hashlib
import time
from typing import Sequence

from src.graph import Span, ThoughtGraph
from src.interfaces import (
    SCORE_CONTRACT_VERSION,
    Contradiction,
    EdgePathMatch,
    Explanation,
    ItemProvenance,
    NodeMatch,
    RelationMatch,
    RetrievalFlags,
    ScoreVector,
    SeedCorrespondence,
    VerifierResult,
    ConfigRef,
)

from . import rrwm as _rrwm
from ._hungarian import solve as hungarian
from ._view import GraphView, node_affinity
from .fgw import solve_fgw
from .paths import guarded_path_matches
from src import scoring

COMPONENT_VERSION = "resonance-verifier/0.2"

DEFAULT_CONFIG = {
    "solver": "multirel_fgw_cg",          # or "qap_rrwm"
    "alpha": 0.7,
    "max_iters": 60,
    "affinity_weights": {"role": 0.5, "label": 0.35, "knowledge": 0.15},
    "unmatched_affinity_floor": 0.05,     # pairs below this affinity may stay unmatched
    "path_matching": "guarded",           # or "off"
    "local_moves": 200,
    "restarts": "unseeded+seeded",
    "hard_conflict_confidence": scoring.HARD_CONF,
    "score_model": scoring.SCORE_MODEL_VERSION,
    "classify_policy": scoring.CLASSIFY_POLICY,
}


def _config_hash(config: dict) -> str:
    return hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class MultiRelFGWVerifier:
    """v0.1 prototype-default verifier (ADR-0003)."""

    def __init__(self, config: dict | None = None):
        self.config = dict(DEFAULT_CONFIG)
        if config:
            self.config.update(config)
        self.config_hash = _config_hash(self.config)
        self.last_latency_seconds = 0.0
        self._rarity: float | None = None

    # -- StructuralVerifier protocol ---------------------------------------
    def verify(self, query: ThoughtGraph, candidate: ThoughtGraph, *,
               seeds: Sequence[SeedCorrespondence] = (),
               rarity: float | None = None) -> VerifierResult:
        """``rarity`` is the corpus-relative rarity of the query skeleton
        (index.motif_rarity); None when no corpus context exists (pairwise
        compare), in which case structure alone may still argue analogy."""
        t0 = time.perf_counter()
        self._rarity = rarity
        va, vb = GraphView(query), GraphView(candidate)
        aff = node_affinity(va, vb, self.config["affinity_weights"])
        seed_triples = tuple(
            (va.index[s.query_node], vb.index[s.candidate_node], s.support)
            for s in seeds
            if s.query_node in va.index and s.candidate_node in vb.index)

        couplings = self._propose(va, vb, aff, seed_triples)
        best = None
        for pi in couplings:
            mapping = self._round(pi, va, vb, aff)
            mapping = self._local_improve(mapping, va, vb)
            candidates = [mapping]
            corrected = self._twin_corrected(mapping, va, vb)
            if corrected is not None:
                candidates.append(corrected)
            for cand_mapping in candidates:
                adj = self._adjudicate(cand_mapping, va, vb)
                if adj.hard_conflicts:
                    alt = self._conflict_free_alternative(cand_mapping, adj, va, vb)
                    if alt is not None:
                        adj = alt
                # Selection stays blind to *structural* contradictions
                # (ADR-0003 #8) but not to label-identity ones: a mapping that
                # aligns structure against unmistakable label twins is worse
                # evidence, not hidden evidence (ADR-0004).
                key = (adj.components["_support_quality"]
                       - adj.components["_label_contradiction"],
                       -adj.components["contradiction"],
                       adj.components["r_direct"])
                if best is None or key > best[0]:
                    best = (key, adj)
        adj = best[1]
        result = self._assemble(adj, va, vb)
        self.last_latency_seconds = time.perf_counter() - t0
        return result

    # -- pipeline stages ----------------------------------------------------
    def _propose(self, va, vb, aff, seed_triples):
        if self.config["solver"] == "qap_rrwm":
            return _rrwm.solve_rrwm(va, vb, aff, seeds=seed_triples)
        return solve_fgw(va, vb, aff, alpha=self.config["alpha"],
                         max_iters=self.config["max_iters"], seeds=seed_triples)

    def _round(self, pi, va, vb, aff):
        n, m = va.n, vb.n
        N = max(n, m)
        floor = self.config["unmatched_affinity_floor"]
        cost = [[-pi[i][j] for j in range(N)] for i in range(N)]
        pairs = hungarian(cost)
        out = []
        for (i, j) in pairs:
            # ADR-0003: node-feature dissimilarity must never GATE a candidate
            # pair. A coupling-backed assignment is kept regardless of
            # affinity (structure earned it); the affinity anchor (>= 0.5)
            # only rescues mass-starved pairs. The old `aff >= floor` gate
            # silently excluded role-noisy cross-domain nodes -- caught by the
            # first raw-text E2E, not by the fixtures, whose roles align by
            # construction.
            if i < n and j < m and (pi[i][j] > 1e-12 or aff[i][j] >= 0.5):
                # A high-affinity pair chosen by the assignment stays claimed
                # even when the relaxation starved its mass: the adjudicator,
                # not the solver, judges the resulting conflicts. This adds
                # claims; it never deletes structurally-supported ones, so it
                # is not a semantic mask.
                out.append((i, j))
        # Greedy anchor completion: a query node the relaxation left in the
        # padding still gets its strong-affinity partner (>= 0.5) when one is
        # free. Additive only; conflicts surface at adjudication.
        used_q = {i for i, _ in out}
        used_c = {j for _, j in out}
        for i in range(n):
            if i in used_q:
                continue
            best_j, best_a = -1, 0.5
            for j in range(m):
                if j in used_c:
                    continue
                if aff[i][j] > best_a or (aff[i][j] == best_a and best_j == -1):
                    best_j, best_a = j, aff[i][j]
            if best_j >= 0 and aff[i][best_j] >= 0.5:
                out.append((i, best_j))
                used_q.add(i)
                used_c.add(best_j)
        return sorted(out)

    def _twin_corrected(self, mapping, va, vb):
        """Re-pair nodes with unmistakable label twins (surface >= T_TWIN).

        Additive/swap only: a query node whose twin is free takes it; when the
        twin is held by another query node with a weak label match, the two
        swap partners. Returns None when nothing changes.
        """
        from src.semantics import compare as _compare
        pairs = dict(mapping)
        inverse = {j: i for i, j in pairs.items()}
        changed = False
        for i in range(va.n):
            best = None
            for j in range(vb.n):
                sim = _compare(va.nodes[i].label, vb.nodes[j].label).surface
                if sim >= scoring.T_TWIN and (best is None or sim > best[1]):
                    best = (j, sim)
            if best is None:
                continue
            j = best[0]
            if pairs.get(i) == j:
                continue
            holder = inverse.get(j)
            if holder is not None and \
               _compare(va.nodes[holder].label, vb.nodes[j].label).fused >= scoring.T_TWIN_CHOSEN:
                continue                       # the twin is legitimately taken
            old_j = pairs.get(i)
            pairs[i] = j
            inverse[j] = i
            if holder is not None:
                if old_j is not None:
                    pairs[holder] = old_j
                    inverse[old_j] = holder
                else:
                    del pairs[holder]
            elif old_j is not None:
                inverse.pop(old_j, None)
            changed = True
        if not changed:
            return None
        return sorted(pairs.items())

    def _structural_key(self, mapping, va, vb):
        adj = scoring.adjudicate(va, vb, mapping, rarity=self._rarity)
        return adj.components["structural"], adj

    def _local_improve(self, mapping, va, vb):
        """Bounded drop-cleanup against the exact structural score.

        A pair contributing preserved relation evidence may NOT be dropped:
        dropping mapped-but-conflicting evidence to erase contradictions is
        the "local yes, global no" failure mode (ADR-0003 #8/E1); the verifier
        must report the conflict, not un-claim the correspondence. Only pairs
        with zero preserved incident relations (junk matches) are droppable.
        """
        budget = self.config["local_moves"]
        score, adj = self._structural_key(mapping, va, vb)
        improved = True
        while improved and budget > 0:
            improved = False
            evidenced_q = set()
            evidenced_c = set()
            for (q_rel, c_rel, _w) in adj.preserved:
                qr = va.rel_by_id[q_rel]
                cr = vb.rel_by_id[c_rel]
                evidenced_q.add(va.index[qr.source]); evidenced_q.add(va.index[qr.target])
                evidenced_c.add(vb.index[cr.source]); evidenced_c.add(vb.index[cr.target])
            # A pair implicated in a contradiction may not be dropped either:
            # deleting the witness hides the conflict instead of adjudicating
            # it (the same local-yes-global-no dodge, second entrance).
            for con in adj.contradictions:
                if con.kind == "label_identity":      # node-level witness (v0.2)
                    evidenced_q.add(va.index[con.query_item])
                    evidenced_c.add(vb.index[con.candidate_item])
                    continue
                qr = va.rel_by_id[con.query_item]
                cr = vb.rel_by_id[con.candidate_item]
                evidenced_q.add(va.index[qr.source]); evidenced_q.add(va.index[qr.target])
                evidenced_c.add(vb.index[cr.source]); evidenced_c.add(vb.index[cr.target])
            for k in range(len(mapping)):
                i, j = mapping[k]
                if i in evidenced_q or j in evidenced_c:
                    continue
                budget -= 1
                trial = mapping[:k] + mapping[k + 1:]
                s2, adj2 = self._structural_key(trial, va, vb)
                if s2 > score + 1e-12:
                    mapping, score, adj = trial, s2, adj2
                    improved = True
                    break
                if budget <= 0:
                    break
        return mapping

    def _adjudicate(self, mapping, va, vb):
        preserved_ids = {q for (q, _, _) in scoring.adjudicate(va, vb, mapping, rarity=self._rarity).preserved}
        paths = ()
        if self.config["path_matching"] == "guarded":
            paths = tuple(guarded_path_matches(va, vb, list(mapping), preserved_ids))
        return scoring.adjudicate(va, vb, mapping, paths, rarity=self._rarity)

    def _conflict_free_alternative(self, mapping, adj, va, vb):
        """ADR-0003: on a hard sign conflict, search for a DIFFERENT mapping
        before rejecting -- a re-assignment, never an un-assignment. Dropping
        the conflicting endpoints and keeping the rest would be the
        local-yes-global-no dodge, so an alternative is valid only if it maps
        at least as many nodes, has no hard conflict, and still passes the
        structural threshold."""
        banned = set()
        for c in adj.hard_conflicts:
            rel = va.rel_by_id[c.query_item]
            i = va.index[rel.source]
            j_rel = vb.rel_by_id[c.candidate_item]
            banned.add((i, vb.index[j_rel.source]))
            i2 = va.index[rel.target]
            banned.add((i2, vb.index[j_rel.target]))
        cur = dict(mapping)
        trial_pairs = [(i, j) for (i, j) in mapping if (i, j) not in banned]
        freed_q = sorted(set(cur) - {i for i, _ in trial_pairs})
        used_c = {j for _, j in trial_pairs}
        aff = node_affinity(va, vb, self.config["affinity_weights"])
        floor = self.config["unmatched_affinity_floor"]
        for qi in freed_q:
            best = None
            for cj in range(vb.n):
                if cj in used_c or (qi, cj) in banned or aff[qi][cj] < floor:
                    continue
                t = self._adjudicate(sorted(trial_pairs + [(qi, cj)]), va, vb)
                if t.hard_conflicts:
                    continue
                key = t.components["structural"]
                if best is None or key > best[0]:
                    best = (key, cj)
            if best is not None:
                trial_pairs.append((qi, best[1]))
                used_c.add(best[1])
        if len(trial_pairs) < len(mapping):
            return None
        cand = self._adjudicate(sorted(trial_pairs), va, vb)
        if not cand.hard_conflicts and \
           cand.components["structural"] >= scoring.T_STRUCTURE and \
           cand.components["_support_quality"] >= adj.components["_support_quality"] - 1e-9:
            return cand
        return None

    # -- assembly -----------------------------------------------------------
    def _assemble(self, adj, va, vb) -> VerifierResult:
        def prov(view, item_id, spans):
            return ItemProvenance(
                thought_id=view.graph.thought_id, item_id=item_id,
                provenance_kind=view.graph.provenance.kind,
                spans=tuple(spans))

        mapping = tuple(
            NodeMatch(
                query_node=va.nodes[i].id, candidate_node=vb.nodes[j].id,
                support=1.0,
                query_provenance=prov(va, va.nodes[i].id, va.nodes[i].spans),
                candidate_provenance=prov(vb, vb.nodes[j].id, vb.nodes[j].spans))
            for (i, j) in adj.mapping)
        matched = tuple(
            RelationMatch(
                query_relation=q, candidate_relation=c, support=w,
                query_provenance=prov(va, q, va.rel_by_id[q].spans),
                candidate_provenance=prov(vb, c, vb.rel_by_id[c].spans))
            for (q, c, w) in adj.preserved)
        edge_paths = tuple(
            EdgePathMatch(
                query_relation=pm.query_relation,
                candidate_relations=pm.candidate_relations,
                realizes_nodes=pm.realizes_nodes,
                support=pm.support,
                query_provenance=prov(va, pm.query_relation,
                                      va.rel_by_id[pm.query_relation].spans),
                candidate_provenances=tuple(
                    prov(vb, rid, vb.rel_by_id[rid].spans)
                    for rid in pm.candidate_relations),
                realizes_node_provenances=tuple(
                    prov(vb, nid, vb.nodes[vb.index[nid]].spans)
                    for nid in pm.realizes_nodes))
            for pm in adj.path_matches)
        mapped_q = {m.query_node for m in mapping}
        mapped_c = {m.candidate_node for m in mapping}
        matched_q_rels = {m.query_relation for m in matched} | {p.query_relation for p in edge_paths}
        matched_c_rels = {m.candidate_relation for m in matched} | {
            rid for p in edge_paths for rid in p.candidate_relations}
        def item_spans(view, item_id):
            if item_id in view.rel_by_id:
                return view.rel_by_id[item_id].spans
            return view.nodes[view.index[item_id]].spans

        contradictions = tuple(
            Contradiction(
                kind=c.kind, query_item=c.query_item, candidate_item=c.candidate_item,
                contribution=c.contribution, rule_version=COMPONENT_VERSION,
                query_provenance=prov(va, c.query_item, item_spans(va, c.query_item)),
                candidate_provenance=prov(vb, c.candidate_item, item_spans(vb, c.candidate_item)))
            for c in adj.contradictions)
        comp = adj.components
        vector = ScoreVector(
            structural=comp["structural"], semantic=comp["semantic"],
            knowledge_about=comp["knowledge_about"],
            knowledge_requires=comp["knowledge_requires"],
            complement_query_to_candidate=comp["complement_query_to_candidate"],
            complement_candidate_to_query=comp["complement_candidate_to_query"],
            coverage_containment=comp["coverage_containment"],
            coverage_symmetric=comp["coverage_symmetric"],
            contradiction=comp["contradiction"], evidence_gate=comp["evidence_gate"],
            n_role=comp["n_role"], r_direct=comp["r_direct"],
            r_direct_unweighted=comp["r_direct_unweighted"], r_path=comp["r_path"],
            y_systematicity=comp["y_systematicity"],
            h_sign_conflict=comp["h_sign_conflict"], e_nodes=comp["e_nodes"],
            e_relations=comp["e_relations"],
            knowledge_evidence_present=comp["knowledge_evidence_present"],
            rarity_weighting=comp["rarity_weighting"],
            extras={"surface_semantic": comp["surface_semantic"],
                    "concept_alignment": comp["concept_alignment"],
                    "domain_overlap": comp["domain_overlap"],
                    "rarity": comp["rarity"],
                    "n_role_exact": comp["n_role_exact"]})
        hard_rejection = None
        if comp["h_sign_conflict"]:
            worst = max(adj.hard_conflicts, key=lambda c: c.contribution)
            hard_rejection = f"{worst.kind}:{worst.query_item}->{worst.candidate_item}"
        classification = scoring.classify(comp)
        confidence = scoring.confidence(comp, classification)
        solver_config = ConfigRef(
            component="r4-verifier/" + self.config["solver"],
            component_version=COMPONENT_VERSION,
            config_hash=self.config_hash)
        explanation = Explanation(
            mapping=mapping, matched_relations=matched, edge_path_matches=edge_paths,
            unmatched_query_nodes=tuple(n.id for n in va.nodes if n.id not in mapped_q),
            unmatched_candidate_nodes=tuple(n.id for n in vb.nodes if n.id not in mapped_c),
            unmatched_query_relations=tuple(r.id for r in va.relations
                                            if r.id not in matched_q_rels),
            unmatched_candidate_relations=tuple(r.id for r in vb.relations
                                                if r.id not in matched_c_rels),
            contradictions=contradictions, retrieval_channels=(),
            systematicity_systems=adj.systematicity_systems,
            score_model_version=SCORE_CONTRACT_VERSION,
            schema_version=va.graph.schema_version,
            config_hash=self.config_hash)
        return VerifierResult(
            contract_version=SCORE_CONTRACT_VERSION,
            query_id=va.graph.thought_id, candidate_id=vb.graph.thought_id,
            candidate_config=self.config_hash,
            mapping=mapping, matched_relations=matched, edge_path_matches=edge_paths,
            unmatched_query_nodes=explanation.unmatched_query_nodes,
            unmatched_candidate_nodes=explanation.unmatched_candidate_nodes,
            unmatched_query_relations=explanation.unmatched_query_relations,
            unmatched_candidate_relations=explanation.unmatched_candidate_relations,
            contradictions=contradictions, hard_rejection=hard_rejection,
            components=vector, classification=classification, confidence=confidence,
            explanation=explanation, solver_config=solver_config,
            retrieval_flags=RetrievalFlags())


class RRWMVerifier(MultiRelFGWVerifier):
    """Co-equal gate candidate (ADR-0003): sparse Lawler-QAP via simplified
    reweighted random walks. Same consistency/rounding/adjudication path."""

    def __init__(self, config: dict | None = None):
        merged = {"solver": "qap_rrwm"}
        if config:
            merged.update(config)
        super().__init__(merged)
