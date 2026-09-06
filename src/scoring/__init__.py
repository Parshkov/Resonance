"""Exact adjudicator implementing docs/RESONANCE_SCORING_v0.1.md, revised by
ADR-0004 (scoring policy v0.2).

Evaluates a DISCRETE partial injective mapping; a relaxation objective is
never the final resonance decision (ADR-0003). Deterministic, stdlib-only.

v0.2 changes (ADR-0004):
* ``semantic`` is the deterministic lexicon similarity (concept classes,
  stems, trigrams) instead of raw token Jaccard;
* three new diagnostics in ``extras``: ``surface_semantic`` (same words),
  ``concept_alignment`` (same abstract notions), ``domain_overlap`` (same
  domain anchors), plus corpus ``rarity`` of the query skeleton when the
  caller supplies it;
* the evidence gate is smooth (geometric mean) instead of a hard 5-node /
  4-relation cliff, so small chat-extracted graphs are scored, not zeroed;
* classification separates synonymy (surface/domain high -> direct or
  approximate), analogy (concept alignment high, vocabulary different) and
  template coincidence (structure only -> negative unless the skeleton is
  rare in the corpus and some concept support exists).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from src.alignment._view import RELATION_TYPES, SIGN_OPPOSITES, GraphView, role_compatibility
from src.alignment.scoring_types import PathMatch
from src.semantics import abstract_concepts as _abstract, compare as _compare

SCORE_MODEL_VERSION = "resonance-score/0.2"

# Scoring weights (contract section "Structural Components"); unchanged from v0.1.
W_R_DIRECT, W_R_PATH = 0.75, 0.25
W_N_ROLE, W_R, W_SYST, W_QC, W_QS, W_XCON = 0.10, 0.45, 0.25, 0.15, 0.05, 0.30
HARD_CONF = 0.9          # "calibrated high confidence" for hard sign conflicts
T_TWIN = 0.8             # surface similarity that makes a candidate node a label twin
T_TWIN_CHOSEN = 0.4      # chosen pair at least this similar -> no twin conflict
# Smooth evidence gate saturation points (v0.2): geometric mean of node and
# relation evidence, each saturating at GATE_NODES / GATE_RELATIONS.
GATE_NODES, GATE_RELATIONS = 4.0, 3.0


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


def _best_twin(label: str, others: Sequence[str], *, exclude: int) -> tuple[int, float] | None:
    best: tuple[int, float] | None = None
    for j, other in enumerate(others):
        if j == exclude:
            continue
        sim = _compare(label, other).surface
        if sim >= T_TWIN and (best is None or sim > best[1]):
            best = (j, sim)
    return best


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
    *,
    rarity: float | None = None,
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
        # A candidate relation already consumed by an exact match has been fully
        # explained; re-using it here would let one candidate edge both preserve
        # one query relation and contradict another between the same node pair.
        # With nothing unconsumed left on the candidate side, the remaining query
        # relation is unobserved evidence, not a contradiction (contract). Sign,
        # assertion and direction conflicts stay unfiltered: a directly opposite
        # assertion conflicts with the query whether or not it also matched.
        modal = [r for r in fwd if r.type == rel.type and r.assertion == rel.assertion
                 and r.modality != rel.modality and r.id not in matched_c_rels]
        typed = [r for r in fwd if r.type != rel.type and (rel.type, r.type) not in SIGN_OPPOSITES
                 and r.id not in matched_c_rels]
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

    # Label identity (v0.2, the project's central hard negative): when a node
    # has an unmistakable label twin on the other side but the mapping pairs
    # it (or its twin) with something else, the structures are being aligned
    # *against* the words. That is "same words, different structure"; it is
    # reported as a contradiction and never silently accepted as resonance.
    label_contradiction_mass = 0.0
    seen_twin: set[tuple[str, str]] = set()
    for (i, ci) in mapping_pairs:
        chosen = _compare(va.nodes[i].label, vb.nodes[ci].label).fused
        if chosen >= T_TWIN_CHOSEN:
            continue
        # query node i has a better twin elsewhere in the candidate
        twin_j = _best_twin(va.nodes[i].label, [vb.nodes[j].label for j in range(vb.n)], exclude=ci)
        if twin_j is not None:
            key = (va.nodes[i].id, vb.nodes[twin_j[0]].id)
            if key not in seen_twin:
                seen_twin.add(key)
                w = min(va.nodes[i].extract_conf, vb.nodes[twin_j[0]].extract_conf) * twin_j[1]
                contradictions.append(ContradictionRec("label_identity", key[0], key[1], w))
                label_contradiction_mass += w
        # candidate node ci has a better twin elsewhere in the query
        twin_i = _best_twin(vb.nodes[ci].label, [va.nodes[q].label for q in range(va.n)], exclude=i)
        if twin_i is not None:
            key = (va.nodes[twin_i[0]].id, vb.nodes[ci].id)
            if key not in seen_twin:
                seen_twin.add(key)
                w = min(va.nodes[twin_i[0]].extract_conf, vb.nodes[ci].extract_conf) * twin_i[1]
                contradictions.append(ContradictionRec("label_identity", key[0], key[1], w))
                label_contradiction_mass += w

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
            * role_compatibility(va.nodes[i].role, vb.nodes[j].role)
            for i, j in mapping_pairs) / n_mapped
        n_role_exact = sum(1.0 for i, j in mapping_pairs if va.nodes[i].role == vb.nodes[j].role) / n_mapped
    else:
        n_role = 0.0
        n_role_exact = 0.0

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
    evidence_gate = math.sqrt(min(1.0, e_nodes / GATE_NODES) * min(1.0, e_relations / GATE_RELATIONS))

    # v0.2: guarded path credit is *additional* to direct credit (both are
    # normalised by the same query relation mass), so a perfect isomorphism
    # earns the full relational weight instead of 75% of it.
    r_combined = min(1.0, r_direct + r_path)
    # v0.2: role agreement and coverage are *conditional* on relational
    # evidence. A mapping that preserves no relation is not resonance however
    # many nodes it pairs, so those terms scale with sqrt(R) and vanish at R=0.
    relational_support = math.sqrt(max(0.0, min(1.0, r_combined)))
    structural_raw = (relational_support * (W_N_ROLE * n_role + W_QC * q_containment + W_QS * q_symmetric)
                      + W_R * r_combined + W_SYST * y_syst - W_XCON * x_contra)
    structural = 0.0 if h_sign else evidence_gate * max(0.0, min(1.0, structural_raw))
    # Conflict-blind support quality: used ONLY to choose between candidate
    # mappings, never as a public score. Selecting by the X-subtracted score
    # would reward hiding conflicts behind weaker mappings (E1 / ADR-0003 #8).
    support_quality = evidence_gate * max(0.0, min(1.0, structural_raw + W_XCON * x_contra))

    # ---- non-structural ----------------------------------------------------
    if n_mapped:
        sims = [_compare(va.nodes[i].label, vb.nodes[j].label) for i, j in mapping_pairs]
        s_semantic = sum(x.fused for x in sims) / n_mapped
        s_surface = sum(x.surface for x in sims) / n_mapped
        s_domain = sum(x.domain for x in sims) / n_mapped
        # Concept alignment is averaged over pairs the lexicon can actually
        # speak about (both labels carry an abstract class) and discounted by
        # the square root of that coverage: lexicon silence is missing
        # evidence, not evidence of difference, but low coverage still caps
        # what an analogy claim may rest on. Template coincidences (no
        # abstract classes at all) get coverage 0 and therefore 0.
        # A label encoder (src/semantics/neural.py), when active, has already
        # raised `concept` on these pairs inside compare(); coverage stays the
        # lexicon's, so templated labels that an encoder finds alike cannot
        # manufacture an analogy, and the frozen gates hold either way.
        covered = [x.concept for (i, j), x in zip(mapping_pairs, sims)
                   if _abstract(va.nodes[i].label) and _abstract(vb.nodes[j].label)]
        coverage = len(covered) / n_mapped
        s_concept = (sum(covered) / len(covered)) * math.sqrt(coverage) if covered else 0.0
    else:
        s_semantic = s_surface = s_concept = s_domain = 0.0
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
        "knowledge_evidence_present": know_present, "rarity_weighting": rarity is not None,
        "complement_query_to_candidate": k_qc, "complement_candidate_to_query": k_cq,
        "surface_semantic": s_surface, "concept_alignment": s_concept, "domain_overlap": s_domain,
        "rarity": 1.0 if rarity is None else max(0.0, min(1.0, rarity)),
        "n_role_exact": n_role_exact,
        "_support_quality": support_quality,
        "_label_contradiction": (label_contradiction_mass / denom) if denom else 0.0,
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


# Classification thresholds (scoring policy v0.2, ADR-0004). Calibrated on
# Benchmark v0.2 skeletons S1-S4 only; S5-S8 are the untouched gate split.
T_STRUCTURE = 0.25
T_CONTRADICTION = 0.15
T_ABOUT = 0.20
T_COMP = 0.30
T_SAME_WORDS = 0.30          # surface similarity that marks "same vocabulary"
T_SAME_DOMAIN = 0.30         # domain-anchor overlap that marks "same domain"
T_CONCEPT_ANALOGY = 0.25     # abstract-concept alignment required for analogy (calibration gap 0.0..0.42)
T_CONCEPT_WEAK = 0.12        # minimal concept support for a rare-skeleton analogy
T_RARE_SKELETON = 0.55       # corpus rarity above which structure alone may argue
T_ANALOGICAL_STRUCTURE = 0.80
# Same subject, nothing contradicted: a lower bar on whole-graph structure.
#
# `structural` compares wholes, so it falls as one person's picture grows --
# which is how someone working on one piece of your problem came back
# "negative". Measured on that pair: structural 0.228, semantic 0.561,
# contradiction 0.0, one relation of three preserved.
#
# Containment was tried first and is the wrong signal: the demo corpus's
# vocabulary trap -- same words, wrong structure, which must stay negative --
# also has coverage_containment 1.0. Semantic agreement is what separates
# them, 0.561 against 0.082, and it is what this reads.
T_STRUCTURE_SAME_SUBJECT = 0.15
T_SAME_SUBJECT_SEMANTIC = 0.40
T_DIRECT_COVERAGE = 0.80

CLASSIFY_POLICY = "scoring-v0.2-concept-aligned-analogy/0.2"

# Every verdict `classify` can return, declared once so that the places which
# have to put these into words cannot fall behind the engine.
#
# They did. The chat and the page carried a phrase for "literal", which this
# module never returns, and none for "direct" or "complementary", which it
# does -- so two people working on the same subject were told they were a
# "direct", and the pair where each holds what the other lacks was told
# "complementary". The one verdict with human words was "analogical", which is
# why the product read as though it only wanted people from another field.
CLASSIFICATIONS = ("direct", "approximate", "analogical", "complementary", "negative")


def _direct_or_approximate(components: dict) -> str:
    if (components["r_direct"] >= 0.999 and components["contradiction"] == 0.0
            and components["coverage_symmetric"] >= 0.999
            and components.get("n_role_exact", 1.0) >= 0.999
            and not components["h_sign_conflict"]):
        return "direct"
    return "approximate"


def classify(components: dict) -> str:
    if components["complement_query_to_candidate"] >= T_COMP or \
       components["complement_candidate_to_query"] >= T_COMP:
        return "complementary"
    if components["h_sign_conflict"]:
        return "negative"
    surface = components.get("surface_semantic", components["semantic"])
    domain = components.get("domain_overlap", 0.0)
    concept = components.get("concept_alignment", 0.0)
    floor = T_STRUCTURE
    if (components["semantic"] >= T_SAME_SUBJECT_SEMANTIC
            and components["contradiction"] == 0.0
            and components["r_direct"] > 0.0):
        # Two people plainly on the same subject, with a relation in common and
        # nothing contradicted. Whole-graph structure is the wrong ruler here:
        # it measures how alike the pictures are, and the person working on one
        # part of your problem necessarily has a smaller one.
        floor = T_STRUCTURE_SAME_SUBJECT
    if components["structural"] < floor or components["contradiction"] > T_CONTRADICTION:
        return "negative"
    # Corpus rarity is a claim about a corpus: without one (pairwise compare)
    # structure alone may not argue analogy, whatever the default value says.
    rarity = components.get("rarity", 0.0) if components.get("rarity_weighting") else 0.0
    if components.get("_about_evidence"):
        # Scoring v0.1 knowledge rule, verbatim: shared "about" concepts mean
        # the same subject matter; disjoint "about" concepts mean analogy.
        if components["knowledge_about"] < T_ABOUT:
            return "analogical"
        return _direct_or_approximate(components)
    if surface >= T_SAME_WORDS or domain >= T_SAME_DOMAIN:
        return _direct_or_approximate(components)
    # different vocabulary and different domain: analogy needs abstract-concept
    # correspondence; bare skeleton agreement is a template coincidence unless
    # the skeleton itself is rare in the corpus and some concept support exists.
    if concept >= T_CONCEPT_ANALOGY:
        return "analogical"
    if (components["structural"] >= T_ANALOGICAL_STRUCTURE and rarity >= T_RARE_SKELETON
            and concept >= T_CONCEPT_WEAK):
        return "analogical"
    return "negative"


def confidence(components: dict, classification: str) -> str:
    """Three-level confidence from evidence mass, threshold margin and conflicts."""
    gate = components["evidence_gate"]
    structural = components["structural"]
    contradiction = components["contradiction"]
    if classification == "negative":
        margin = T_STRUCTURE - structural if not components["h_sign_conflict"] else 1.0
    else:
        margin = structural - T_STRUCTURE
    if gate < 0.5 or abs(margin) < 0.08 or contradiction > 0.10:
        return "low"
    if gate >= 0.9 and abs(margin) >= 0.25 and contradiction == 0.0:
        return "high"
    return "medium"
