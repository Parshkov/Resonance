"""Exact adjudicator implementing docs/RESONANCE_SCORING_v0.1.md.

Evaluates a DISCRETE partial injective mapping; a relaxation objective is
never the final resonance decision (ADR-0003). Deterministic, stdlib-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.alignment._view import RELATION_TYPES, SIGN_OPPOSITES, GraphView
from src.alignment.scoring_types import PathMatch

SCORE_MODEL_VERSION = "resonance-score/0.1"

# Frozen v0.1 scoring weights (contract section "Structural Components").
W_R_DIRECT, W_R_PATH = 0.75, 0.25
W_N_ROLE, W_R, W_SYST, W_QC, W_QS, W_XCON = 0.10, 0.45, 0.25, 0.15, 0.05, 0.30
HARD_CONF = 0.9          # "calibrated high confidence" for hard sign conflicts


@dataclass(frozen=True)
class ContradictionRec:
    kind: str
    query_item: str
    candidate_item: str
    contribution: float


@dataclass(frozen=True)
class Adjudication:
    mapping: tuple[tuple[int, int], ...]
    preserved: tuple[tuple[str, str, float], ...]      # (q_rel_id, c_rel_id, weight)
    path_matches: tuple[PathMatch, ...]
    contradictions: tuple[ContradictionRec, ...]
    hard_conflicts: tuple[ContradictionRec, ...]
    components: dict
    systematicity_systems: tuple[tuple[str, ...], ...]


def _induced(view: GraphView, mapping: dict[int, int]):
    """Directed relation instances between mapped node pairs, both graphs."""
    out = []
    for (i, j), rels in view.rels_between.items():
        if i in mapping and j in mapping:
            for rel in rels:
                out.append((i, j, rel))
    return out


def adjudicate(
    va: GraphView,
    vb: GraphView,
    mapping_pairs: Sequence[tuple[int, int]],
    path_matches: Sequence[PathMatch] = (),
) -> Adjudication:
    mapping = dict(mapping_pairs)
    inv = {j: i for i, j in mapping_pairs}
    preserved: list[tuple[str, str, float]] = []
    contradictions: list[ContradictionRec] = []
    hard: list[ContradictionRec] = []
    matched_c_rels: set[str] = set()

    q_induced = _induced(va, mapping)
    # Query relations are obligations: ALL of them stay in the denominator so
    # un-mapping a problem node can never shrink what must be explained.
    # Candidate mass stays induced-only (containment: candidate may be a whole
    # around a query fragment).
    total_q_mass = sum(rel.extract_conf for rel in va.relations)
    c_mass = 0.0
    for (ci, cj), rels in vb.rels_between.items():
        if ci in inv and cj in inv:
            c_mass += sum(rel.extract_conf for rel in rels)

    for (i, j, rel) in q_induced:
        ci, cj = mapping[i], mapping[j]
        fwd = [r for r in vb.rels_between.get((ci, cj), [])]
        rev = [r for r in vb.rels_between.get((cj, ci), [])]
        exact = [r for r in fwd
                 if r.type == rel.type and r.assertion == rel.assertion
                 and r.modality == rel.modality and r.id not in matched_c_rels]
        if exact:
            best = exact[0]
            matched_c_rels.add(best.id)
            preserved.append((rel.id, best.id, min(rel.extract_conf, best.extract_conf)))
            continue
        conf = rel.extract_conf
        sign = [r for r in fwd if (rel.type, r.type) in SIGN_OPPOSITES]
        flipped = [r for r in fwd if r.type == rel.type and r.assertion != rel.assertion]
        reversed_ = [r for r in rev if r.type == rel.type and r.assertion == rel.assertion]
        modal = [r for r in fwd if r.type == rel.type and r.assertion == rel.assertion
                 and r.modality != rel.modality]
        typed = [r for r in fwd if r.type != rel.type and (rel.type, r.type) not in SIGN_OPPOSITES]
        if sign:
            rec = ContradictionRec("relation_type", rel.id, sign[0].id,
                                   min(conf, sign[0].extract_conf))
            contradictions.append(rec)
            if min(conf, sign[0].extract_conf) >= HARD_CONF:
                hard.append(rec)
        elif flipped:
            rec = ContradictionRec("assertion", rel.id, flipped[0].id,
                                   min(conf, flipped[0].extract_conf))
            contradictions.append(rec)
            if min(conf, flipped[0].extract_conf) >= HARD_CONF:
                hard.append(rec)
        elif reversed_:
            rec = ContradictionRec("direction", rel.id, reversed_[0].id,
                                   min(conf, reversed_[0].extract_conf))
            contradictions.append(rec)
            if min(conf, reversed_[0].extract_conf) >= HARD_CONF:
                hard.append(rec)
        elif modal:
            contradictions.append(ContradictionRec(
                "modality", rel.id, modal[0].id, 0.5 * min(conf, modal[0].extract_conf)))
        elif typed:
            contradictions.append(ContradictionRec(
                "relation_type", rel.id, typed[0].id, 0.5 * min(conf, typed[0].extract_conf)))
        # else: unmatched evidence, not a contradiction (contract).

    path_rel_ids = {pm.query_relation for pm in path_matches}
    preserved_ids = {q for (q, _, _) in preserved}

    # global consistency: both graphs assert typed structure from the same
    # mapped node over mapped nodes, but to different targets/sources. One
    # empty side is unobserved evidence, never a contradiction (contract).
    seen_global: set[tuple] = set()
    for (i, ci) in mapping_pairs:
        for t in RELATION_TYPES:
            for direction in ("out", "in"):
                q_edges = [(j, rel) for ((s_, j), rels2) in va.rels_between.items()
                           if s_ == i for rel in rels2 if rel.type == t] if direction == "out" else                           [(s_, rel) for ((s_, j), rels2) in va.rels_between.items()
                           if j == i for rel in rels2 if rel.type == t]
                q_proj = {mapping[j] for (j, _r) in q_edges if j in mapping}
                c_edges = [(j, rel) for ((s_, j), rels2) in vb.rels_between.items()
                           if s_ == ci for rel in rels2 if rel.type == t] if direction == "out" else                           [(s_, rel) for ((s_, j), rels2) in vb.rels_between.items()
                           if j == ci for rel in rels2 if rel.type == t]
                c_proj = {j for (j, _r) in c_edges if j in inv}
                if not q_proj or not c_proj:
                    continue
                if q_proj == c_proj:
                    continue
                only_q = q_proj - c_proj
                only_c = c_proj - q_proj
                for (j, rel) in q_edges:
                    if j in mapping and mapping[j] in (q_proj - c_proj):
                        for (cj2, crel) in c_edges:
                            if cj2 in only_c:
                                key = (rel.id, crel.id)
                                if key in seen_global:
                                    continue
                                seen_global.add(key)
                                contradictions.append(ContradictionRec(
                                    "global_consistency", rel.id, crel.id,
                                    min(rel.extract_conf, crel.extract_conf)))
                                break

    # ---- components -------------------------------------------------------
    n_mapped = len(mapping_pairs)
    if n_mapped:
        n_role = sum(
            min(va.nodes[i].extract_conf, vb.nodes[j].extract_conf)
            * (1.0 if va.nodes[i].role == vb.nodes[j].role else 0.0)
            for i, j in mapping_pairs) / n_mapped
    else:
        n_role = 0.0

    preserved_mass = sum(w for (_, _, w) in preserved)
    denom = max(total_q_mass, c_mass)
    r_direct = preserved_mass / denom if denom else 0.0
    r_direct_unweighted = (len(preserved) / max(len(q_induced), 1)) if q_induced else 0.0

    path_mass = sum(pm.support for pm in path_matches)
    # R_path normalised against query relations with mapped endpoints that
    # direct matching could not cover; zero when no guarded match is used.
    uncovered = [(_i, _j, rel) for (_i, _j, rel) in q_induced if rel.id not in preserved_ids]
    r_path = min(1.0, path_mass / max(total_q_mass, 1e-9)) if path_matches else 0.0

    # systematicity: connected components over preserved query relations
    # (nodes shared between preserved relations connect them).
    edges_of = {q: (va.rel_by_id[q].source, va.rel_by_id[q].target) for (q, _, _) in preserved}
    parent = {q: q for q in edges_of}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    endpoint_owner: dict[str, str] = {}
    for q, (s, t) in edges_of.items():
        for endpoint in (s, t):
            if endpoint in endpoint_owner:
                ra, rb2 = find(endpoint_owner[endpoint]), find(q)
                if ra != rb2:
                    parent[ra] = rb2
            else:
                endpoint_owner[endpoint] = q
    systems: dict[str, list[str]] = {}
    for q in edges_of:
        systems.setdefault(find(q), []).append(q)
    system_tuples = tuple(tuple(sorted(v)) for _, v in sorted(systems.items()))
    if preserved:
        connected_mass = sum(w for (q, _, w) in preserved
                             if len(systems[find(q)]) >= 2)
        y_syst = (connected_mass + 0.5 * (preserved_mass - connected_mass)) / preserved_mass
    else:
        y_syst = 0.0

    q_containment = n_mapped / min(va.n, vb.n) if min(va.n, vb.n) else 0.0
    q_symmetric = 2.0 * n_mapped / (va.n + vb.n) if (va.n + vb.n) else 0.0
    x_contra = min(1.0, sum(c.contribution for c in contradictions) / denom) if denom else 0.0
    h_sign = bool(hard)

    e_nodes = float(n_mapped)
    # Effective relation evidence: repeated occurrences of one v0.1 pattern
    # (source_role, type, target_role, assertion, modality) diminish, so a
    # monotype generic chain cannot buy the same evidence as diverse preserved
    # structure. First occurrence keeps full weight; repeats keep 0.25.
    pattern_seen: dict[tuple, int] = {}
    e_rel_effective = 0.0
    for (q, _c, w) in preserved:
        rel = va.rel_by_id[q]
        pat = (va.nodes[va.index[rel.source]].role, rel.type,
               va.nodes[va.index[rel.target]].role, rel.assertion, rel.modality)
        k = pattern_seen.get(pat, 0)
        pattern_seen[pat] = k + 1
        e_rel_effective += w * (1.0 if k == 0 else 0.25)
    e_relations = e_rel_effective + path_mass
    evidence_gate = min(1.0, e_nodes / 5.0) * min(1.0, e_relations / 4.0)

    r_combined = W_R_DIRECT * r_direct + W_R_PATH * r_path
    structural_raw = (W_N_ROLE * n_role + W_R * r_combined + W_SYST * y_syst
                      + W_QC * q_containment + W_QS * q_symmetric - W_XCON * x_contra)
    structural = 0.0 if h_sign else evidence_gate * max(0.0, min(1.0, structural_raw))
    # Conflict-blind support quality: used ONLY to choose between candidate
    # mappings, never as a public score. Selecting by the X-subtracted score
    # would reward hiding conflicts behind weaker mappings (E1 / ADR-0003 #8).
    support_quality = evidence_gate * max(0.0, min(1.0, structural_raw + W_XCON * x_contra))

    # ---- non-structural ----------------------------------------------------
    if n_mapped:
        s_semantic = sum(
            _label_sim(va, vb, i, j) for i, j in mapping_pairs) / n_mapped
    else:
        s_semantic = 0.0
    a_about, b_about = va.about_ids(), vb.about_ids()
    a_req, b_req = va.requires_ids(), vb.requires_ids()
    know_present = bool((a_about | a_req)) and bool((b_about | b_req))
    about_evidence = bool(a_about) and bool(b_about)
    k_about = len(a_about & b_about) / len(a_about | b_about) if (a_about | b_about) else 0.0
    k_req = len(a_req & b_req) / len(a_req | b_req) if (a_req | b_req) else 0.0
    k_qc = len(a_req & b_about) / len(a_req) if a_req else 0.0
    k_cq = len(b_req & a_about) / len(b_req) if b_req else 0.0

    components = {
        "n_role": n_role, "r_direct": r_direct, "r_direct_unweighted": r_direct_unweighted,
        "r_path": r_path, "y_systematicity": y_syst,
        "coverage_containment": q_containment, "coverage_symmetric": q_symmetric,
        "contradiction": x_contra, "h_sign_conflict": h_sign,
        "e_nodes": e_nodes, "e_relations": e_relations, "evidence_gate": evidence_gate,
        "structural": structural, "semantic": s_semantic,
        "knowledge_about": k_about, "knowledge_requires": k_req,
        "knowledge_evidence_present": know_present, "rarity_weighting": False,
        "complement_query_to_candidate": k_qc, "complement_candidate_to_query": k_cq,
        "_support_quality": support_quality,
        "_about_evidence": about_evidence,
    }
    return Adjudication(
        mapping=tuple(mapping_pairs), preserved=tuple(preserved),
        path_matches=tuple(path_matches), contradictions=tuple(contradictions),
        hard_conflicts=tuple(hard), components=components,
        systematicity_systems=system_tuples,
    )


def _label_sim(va: GraphView, vb: GraphView, i: int, j: int) -> float:
    ta, tb = va._token_cache[i], vb._token_cache[j]
    if not ta and not tb:
        return 0.0
    union = len(ta | tb)
    return len(ta & tb) / union if union else 0.0


# Frozen v0.1 classification thresholds (calibration-pack parameters).
T_STRUCTURE = 0.25
T_CONTRADICTION = 0.15
T_ABOUT = 0.20
T_COMP = 0.30
T_SEMANTIC_ANALOGICAL = 0.30
T_DIRECT_COVERAGE = 0.80
# An analogy claim carries no semantic support by definition, so it demands
# stronger structural evidence than a same-domain approximate match. Without
# corpus rarity weighting this is the only DNA-native defence against generic
# motif distractors (C3 margin measurement; E1; scoring-contract calibration
# rule). Calibrated on the v0.1 calibration split: cross-domain analogical
# positives sit at ~0.888, generic distractors at ~0.775-0.785.
T_ANALOGICAL_STRUCTURE = 0.85


# Versioned adjudicator policy, carried in the verifier config hash.
# Primary branch is Scoring v0.1's knowledge rule verbatim. The contract's
# knowledge-absent outcome is "direct_or_analogical_unknown, not forced"; the
# benchmark wire enum forces a choice, so the fallback resolves the unknown
# with the only DNA-native domain proxy available (label semantics), guarded
# by the calibrated analogical-structure floor. Measured basis: v0.1 carries
# 16 `about` refs across 136 graphs (bridge families only) and K_about = 0.0
# on all 128 pairs including paraphrase, so the knowledge branch cannot fire
# outside bridge packs on these fixtures.
CLASSIFY_POLICY = "scoring-v0.1-knowledge-first+semantic-fallback/0.1"


def _direct_or_approximate(components: dict) -> str:
    if (components["r_direct"] >= 0.999 and components["contradiction"] == 0.0
            and components["coverage_symmetric"] >= 0.999
            and not components["h_sign_conflict"]):
        return "direct"
    return "approximate"


def classify(components: dict) -> str:
    if components["complement_query_to_candidate"] >= T_COMP or \
       components["complement_candidate_to_query"] >= T_COMP:
        return "complementary"
    if components["h_sign_conflict"]:
        return "negative"
    if components["structural"] >= T_STRUCTURE and components["contradiction"] <= T_CONTRADICTION:
        if components.get("_about_evidence"):
            # Scoring v0.1 knowledge rule, verbatim.
            if components["knowledge_about"] < T_ABOUT:
                return "analogical"
            return _direct_or_approximate(components)
        # knowledge-absent fallback (versioned policy above)
        if components["semantic"] < T_SEMANTIC_ANALOGICAL:
            return "analogical" if components["structural"] >= T_ANALOGICAL_STRUCTURE else "negative"
        return _direct_or_approximate(components)
    return "negative"
