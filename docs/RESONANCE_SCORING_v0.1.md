# Resonance Scoring and Explanation Contract v0.1

Status: proposed

Date: 2026-08-31

## Principle

Resonance v0.1 returns a score vector and an explanation, not a universal
similarity scalar. Structural, semantic/content, knowledge, complementary,
coverage, evidence, and contradiction signals remain visible. A blended-only
public API is non-conforming: equal-weight `(S_struct + S_sem) / 2` inverts
the project's hard negative on C3/PR #37 numbers, and even a structure-heavy
scalar must not replace the vector. Thresholds and weights are initial
benchmark parameters, not learned truths.

## Required Verifier Output

```json
{
  "contract_version": "resonance-score/0.1",
  "query_id": "q",
  "candidate_id": "c",
  "candidate_config": "immutable-config-hash",
  "retrieval_flags": {
    "requires_structural_verification": true,
    "polarity_reliable": false
  },
  "mapping": [{"query_node": "q1", "candidate_node": "c4"}],
  "matched_relations": [],
  "edge_path_matches": [],
  "unmatched_query_nodes": [],
  "unmatched_candidate_nodes": [],
  "contradictions": [],
  "hard_rejection": null,
  "components": {},
  "classification": "analogical",
  "confidence": "provisional"
}
```

Mappings are partial and mutually injective. Every matched relation or derived
edge-to-path match identifies canonical relation IDs on both sides. A derived
shortcut is never the sole explanation.

## Structural Components

All components are in `[0,1]` before the contradiction subtraction.

- `N_role`: confidence-weighted functional-role compatibility of mapped nodes.
- `R_direct`: confidence- and capped-rarity-weighted F1-like preservation of
  directed, typed, asserted direct relations induced by the mapping. Also report
  an unweighted value.
- `R_path`: guarded edge-to-path preservation. It is zero when no guarded path
  match is used, not silently copied from `R_direct`.
- `Y_systematicity`: fraction of preserved relation evidence belonging to a
  connected mapped system, with higher weight for relations supported by other
  mapped relations than for isolated matches.
- `Q_containment`: `|P|/min(|V_query|,|V_candidate|)` for mapping `P`.
- `Q_symmetric`: `2*|P|/(|V_query|+|V_candidate|)`, reported separately so a
  fragment/whole match is distinguishable from two fully covered graphs.
- `X_contradiction`: confidence-weighted mass of mapped endpoint pairs whose
  direction, relation type, assertion, modality, or role constraints conflict,
  normalized by comparable induced relation mass.
- `H_sign_conflict`: boolean hard boundary for a high-confidence mapped
  `causes`/`prevents`, asserted/negated, or direction/sign inversion.
- `E_nodes`: number of mapped nodes.
- `E_relations`: effective confidence-weighted count of preserved direct or
  guarded path relations.

The initial evidence gate is:

```text
evidence_gate = min(1, E_nodes / 5) * min(1, E_relations / 4)
```

Relation evidence uses a versioned, capped pattern weight. The v0.1 pattern is
`(source_role, relation_type, target_role, assertion, modality)`; connected
two-relation signatures may be evaluated as an ablation, not silently mixed in.

```text
pattern_weight(p) = clamp(log((N + 1) / (df(p) + 1)), 1, W_max)
relation_weight   = extraction_confidence * pattern_weight(p)
```

`N`, `df`, `W_max`, and the corpus snapshot are part of the candidate config.
When no defensible corpus snapshot exists, use weight `1`, set
`rarity_weighting=false`, and report the generic-motif margin. Rarity is a
derived scoring policy, not Thought DNA.

The initial structural score is:

```text
R = 0.75 * R_direct + 0.25 * R_path

structural_raw =
    0.10 * N_role
  + 0.45 * R
  + 0.25 * Y_systematicity
  + 0.15 * Q_containment
  + 0.05 * Q_symmetric
  - 0.30 * X_contradiction

structural_score = evidence_gate * clamp(structural_raw, 0, 1)
```

The formula is evaluated only on a conflict-free final mapping. If
`H_sign_conflict=true`, the adjudicator first searches for a valid alternative
mapping; if none passes, `structural_score=0`, `hard_rejection` records the
conflict, and direct/analogical classification is prohibited. This rule is
required because E1 shows a polarity-flipped near-duplicate can rank above the
true analogue during recall-oriented retrieval.

These values are intentionally structure-heavy and reject accidental one-edge
motifs. They are frozen before the first gate run and may be changed only on
calibration packs. Gate failures are reported before any new version is tuned.

The containment/symmetric split is provisional because C3 measured severe
fragment/whole score drift. No global threshold is accepted until Benchmark
v0.1's 1:2–1:8 size sweep shows that match quality, rather than size ratio,
drives the score.

`R_path` can contribute only through a guarded match licensed by the Invariance
Specification. An unguarded arbitrary path has no structural credit.

## Non-Structural Components

- `S_semantic`: normalized concept/label semantic support for mapped nodes.
- `K_about`: IDF-weighted Jaccard of specific `knowledge.about` IDs.
- `K_requires`: IDF-weighted Jaccard of `knowledge.requires` IDs.
- `K_comp_q_to_c`: directional weighted overlap of query `requires` with
  candidate `about`.
- `K_comp_c_to_q`: the reverse directional overlap.
- `retrieval_semantic`, `retrieval_knowledge`, and `retrieval_structural`:
  raw/calibrated candidate-generator scores, always reported separately.

`S_semantic` and Knowledge DNA do not increase `structural_score`. This is
necessary to distinguish different words/same structure from same words/wrong
structure. Missing knowledge annotations produce `0` plus
`knowledge_evidence_present=false`; they are not contradictions.

## Classification

Threshold symbols below are calibrated on the two calibration packs and then
frozen. Scores across modes are not assumed comparable.

```text
if explicit requires/about bridge and K_comp_q_to_c >= T_comp:
    complementary candidate (direction q -> c)

if not H_sign_conflict and
   structural_score >= T_structure and
   X_contradiction <= T_contradiction:
    if knowledge evidence is present and K_about < T_about:
        analogical
    else:
        direct_or_approximate

if no rule passes:
    negative / unsupported
```

The verifier MAY distinguish `direct` from `approximate` using the calibrated
coverage and unmatched-branch policy. It MUST NOT label a structurally weak pair
analogical merely because its domains differ. Complementary candidates use a
separate directional bridge score and need not be graph-isomorphic.

When Knowledge DNA is absent, a high-structure result is
`direct_or_analogical_unknown`, not forced to one class.

## Contradictions

Each contradiction contains:

- canonical query and candidate item IDs;
- contradiction kind (`direction`, `relation_type`, `assertion`, `modality`,
  `role`, or `global_consistency`);
- confidence-weighted contribution;
- source spans or manual provenance; and
- the rule/version that classified it.

Causal reversal, `causes`/`prevents`, and asserted/negated sign conflicts are
hard rejections at calibrated high confidence. `requires`/`causes` and other
type conflicts contribute to contradiction policy unless separately promoted
to a hard rule. Low-confidence missing relations are unmatched evidence, not
automatically contradictions.

## Explanation Requirements

An accepted result MUST explain:

1. which nodes correspond and the evidence for each pair;
2. which directed typed relations or guarded paths correspond;
3. which connected mapped system generated systematicity credit;
4. which branches are unmatched;
5. which contradictions reduced the score;
6. which candidate channels retrieved the graph;
7. which score/model/schema/config versions were used; and
8. the source provenance behind every displayed item.

The output may include a natural-language rendering, but the structured record
is authoritative and must be reproducible without an LLM.

## Calibration and Failure Rules

- Calibrate thresholds only on designated calibration packs.
- Report every component by benchmark family and stage.
- Ties in structure-over-words comparisons fail.
- No macro average can compensate for a failed anti-invariance.
- Report solver instability across restarts and mapping alternatives.
- Automorphic gold cases accept an explicit set of equivalent mappings rather
  than penalizing an arbitrary valid correspondence.
- If scores from two extraction runs of the same text disagree beyond the
  benchmark tolerance, report extraction failure before matcher failure.

## Related Documents

- [Thought DNA](THOUGHT_DNA_v0.1.md)
- [Invariance Specification](INVARIANCE_SPECIFICATION_v0.1.md)
- [Verification ADR](decisions/ADR-0003-structural-verification.md)
- [Benchmark v0.1](../benchmark/R0_BENCHMARK_v0.1.md)
- [R0 Synthesis](../research/reviews/R0_SYNTHESIS_parshkov-openai-gpt5-codex-s7d3.md)
