# R0 Benchmark v0.1

Status: proposed specification

Date: 2026-08-31

## Objective

Benchmark v0.1 is a contrastive metamorphic architecture gate for Resonance.
It asks whether a frozen candidate system prefers preserved reasoning structure
over shared words, returns the intended partial correspondence, survives named
transformations, rejects meaning-changing controls, and reports failures at the
correct pipeline stage.

It is not a publication dataset, a million-corpus performance claim, or an LLM
similarity-labeling exercise. This document defines the immutable fixture and
metric contract. Gold fixtures are authored and independently reviewed under
this contract; no unreviewed gold score is invented by the synthesis.

## Dataset Shape

Author eight independent 10–14-node seed packs. Each seed has sixteen judged
candidates, for 128 pairs and at most 136 distinct graphs.

- Packs `C01`–`C02`: calibration only.
- Packs `G01`–`G06`: immutable architecture gate.
- No graph or transformed descendant crosses splits.
- Manual judgments are reviewed by a second human before the gate is used.
- The candidate configuration and commit hash are frozen before gate output is
  inspected.

Suggested domains are deliberately diverse: battery degradation, software
retry cascades, organizational coordination, eutrophication, convergent medical
treatment, liquidity cascades, learning prerequisites, and supply-chain
bottlenecks. Domain themes do not define the gold class; mapped directed typed
relations and intent do.

## Sixteen Families per Pack

| # | Family | Gold class | Construction | Primary contract |
|---:|---|---|---|---|
| 1 | paraphrase | direct | change surface wording only | A |
| 2 | vocabulary substitution | approximate | replace concept vocabulary, retain roles/relations | B |
| 3 | irrelevant branch | approximate | add one grounded distractor branch | D |
| 4 | partial graph | approximate | delete 20–30% while recording surviving map | E/G |
| 5 | transparent granularity | approximate | subdivide an edge with `atomic=false` nodes | F conditional |
| 6 | same-domain structural match | direct | manual same-domain relation-preserving candidate | direct resonance |
| 7 | serialization permutation | direct | permute node/edge list order only | C |
| 8 | modest extraction error | approximate | one role/relation error plus one spurious node | I |
| 9 | cross-domain causal analogy | analogical | disjoint concepts, reviewed structural mapping | H verifier |
| 10 | same vocabulary, different structure | negative | rewire/reverse relations, keep labels | anti-invariance |
| 11 | same topic, different intent | negative | retain concepts, change goal/mechanism | anti-invariance |
| 12 | local match, global conflict | negative | preserve local/binary statistics, contradict governing connected system | systematicity / higher-order diagnostic |
| 13 | generic motif distractor | negative | full 8–12-node constellation with the same common role-path bag but wrong intended mapping | collision control |
| 14 | accidental semantic similarity | negative | high word/concept overlap, unrelated relations | semantic shortcut |
| 15 | branch continuation | complementary | candidate extends an explicit open branch | bridge mapping |
| 16 | method/knowledge bridge | complementary | query `requires` matches candidate `about` | directional complement |

Each seed also has two independently generated extraction observations for the
self-match prerequisite. They may reuse family 8's source text but are scored
as extraction artifacts, not as an additional candidate family.

Across the six gate packs, family 10 MUST include at least two one-edge
`causes`/`prevents` polarity flips, two direction reversals, and two broader
rewirings. Retrieval is allowed to surface all six; end-to-end verification must
reject them.

## Files and Schemas

Recommended layout for implemented fixtures:

```text
benchmark/r0-v0.1/
  graphs.jsonl
  pairs.jsonl
  extraction_runs.jsonl
  schema/
    graph.schema.json
    pair.schema.json
    prediction.schema.json
  README.md
```

`graphs.jsonl` contains only valid Thought DNA plus a benchmark graph ID.
Benchmark gold never leaks into engine input.

```json
{
  "case_id": "G01-09",
  "split": "gate",
  "family": "cross_domain_analogy",
  "query_graph": "G01-Q",
  "candidate_graph": "G01-C09",
  "gold_class": "analogical",
  "evaluation_mode": "analogical",
  "relevant": true,
  "gold_node_pairs": [["q1", "c2"]],
  "gold_edge_pairs": [["qe1", "ce4"]],
  "equivalent_mapping_sets": [],
  "bridge_pairs": [],
  "transform_manifest": {},
  "rationale": "reviewed concise rationale",
  "review": {"status": "approved", "reviewer": "public-id"}
}
```

`gold_class` is exactly:

```text
direct | approximate | analogical | complementary | negative
```

Complementary cases populate `bridge_pairs`; they do not fake a graph
isomorphism. Granularity cases may map one canonical edge to an ordered list of
candidate relation IDs. Symmetric cases list acceptable mapping alternatives.
No expected numeric model score is stored.

## Required System Predictions

### Retrieval

For each query and mode:

```text
ranked candidate IDs
per-channel raw/calibrated scores
optional seed correspondences
requires_structural_verification / polarity_reliable flags
index / corpus / feature versions
latency and postings touched
```

### Verification

For each pair:

```text
class and score vector
partial node mapping
matched relation and guarded edge-path mappings
unmatched nodes/relations
contradictions
solver/schema/config versions
latency and restart diagnostics
```

Evaluate the verifier both with the normal retrieval result and with oracle
candidate inclusion. A missed candidate is a retrieval failure; a bad oracle
pair score/mapping is a verifier failure.

## Metrics

- `Recall@K`, macro-averaged by query and reported separately by family/mode.
- Resonance precision after calibration-only threshold selection.
- Negative false-positive rate overall and for every negative family.
- Node correspondence precision/recall/F1 on predicted pair sets.
- Exact-map accuracy plus automorphism-tolerant mapping-set accuracy.
- Directed typed edge-preservation accuracy.
- Guarded edge-to-path accuracy and false-contraction count.
- `Robust@5(f)`: Recall@5 for each transformation family.
- **SOW** (structure-over-words): for each gate seed, both vocabulary-substituted
  and cross-domain positives must score above its same-vocabulary structural
  negative. There are 12 comparisons; ties fail.
- Duplicate-extract span-aligned node and typed-edge F1, hallucination rate, and
  source-span validation rate.
- Runtime, memory, index size, posting-list distribution, postings touched, and
  deterministic replay hash.
- Fragment/whole score stability across size ratios `1:2`, `1:4`, and `1:8`,
  with containment and symmetric coverage reported separately.
- Structural margin `score(noisy_true_analogue) - max(score(generic_motif))`
  by pack, filler world, corpus size, and seed; report minimum and distribution,
  not only pass count.
- Polarity-flip retrieval rank/score and end-to-end rejection rate.

Scores are reported per component under the Scoring Contract. There is no
single aggregate allowed to hide a family failure.

## Mandatory Architecture Gate

A frozen candidate receives a provisional GO only if all applicable checks
pass:

```text
SOW >= 10/12
overall gate Recall@5 >= 0.85
every positive family Recall@5 >= 4/6
resonance precision >= 0.80
overall negative FPR <= 0.10
every negative family false positives <= 1/6
node-pair F1 >= 0.70
directed typed edge accuracy >= 0.75
false meaningful-node contractions == 0
serialization score-vector delta == 0
p95 verifier latency <= 2 s per 50x50 pair on the declared reference CPU
end-to-end polarity-flip rejection == 100%
```

Extraction is a prerequisite:

```text
100% exact span/hash/schema validation
duplicate-extract span-aligned node F1 >= 0.70
duplicate-extract typed-edge F1 >= 0.60
ungrounded extracted objects == 0
```

If extraction fails, downstream retrieval/verifier results are diagnostic only
and do not grant a GO. These thresholds supersede the weaker single-example
floor proposed in R0-F; calibration packs may reveal that the architecture is
not yet viable, not justify moving the gate after inspection.

Complementary retrieval is optional in the first verifier build. If claimed,
require Precision@3 at least `0.67`, correct bridge direction, and no conversion
of a complementary result into structural analogy. If not claimed, report the
mode as unsupported.

## Structural Retrieval Gate

The v0.1 MULTI structural channel must satisfy:

- structural-only cross-domain Recall@20 at least `0.50`;
- intended analogue strictly above every generic-motif distractor in each gate
  pack;
- positive structural margin in every frozen seed/world/size E1 regression, with
  the thin-margin distribution reported;
- the full B design enabled: D0+D1 landmark descriptors, typed directed paths,
  distance buckets, DF/IDF policy, and injective correspondence-consensus
  voting; role-only D0 is a required non-shipping control;
- the exact legacy E1 regression and its Thought-DNA-native companion both
  pass, so toy-only relation entropy cannot grant the gate;
- sublinear postings touched from `10^3` through `10^5` synthetic distractors
  under a fixed 64-feature query budget;
- deterministic seed correspondences and unchanged recall after rerun on the
  same corpus snapshot; and
- `polarity_reliable=false` on structural retrieval output plus 100% verifier
  rejection of the polarity-flip regression before user-visible acceptance.

Failure is a NO-GO for the v0.1 structural retrieval capability and requires an
ADR revision; it does not invalidate the structural verifier.

### E1 executable regression

Retain merged
`research/experiments/R0_E1_fingerprint_discrimination.py` as an executable
regression and extend, rather than rewrite, its evidence matrix:

- worlds `R` (rich random typed graphs) and `Z` (80% bare causal chains);
- the default seed at corpus sizes `10^3`, `10^4`, and `3*10^4` in both worlds;
- three additional fixed, recorded seeds at `10^4` in both worlds, producing
  the 12-case regression matrix, then the scale replay below;
- D0, D1, and MULTI descriptors;
- noisy cross-domain organisation analogue, three bare-chain distractors,
  topology/direction negatives, and the one-edge polarity flip; and
- postings touched, build/query time, live/dead keys, ranks, scores, margin, and
  fortress/tumor motif-family isolation.

PR #36's reference evidence is provenance, not a universal threshold: MULTI
passes the stated kill rule; D0 fails at rich-world `N=10^4`; rich-world margin
is only about `0.009`; and touched postings grow `216 -> 819 -> 1834` for the
default rich-world seed. The synthesis rerun reproduced the ranks/pass results
across 12 world/size/seed configurations. Machine-specific timing differences
must be reported rather than normalized away.

The exact E1 script deliberately remains unchanged, including its toy role and
relation enums. It contains `increases`, `enables`, and `precedes`, which are not
in Thought DNA v0.1's extraction relation set. Add a companion matrix authored
with the exact DNA v0.1 roles/relations (or a reviewed versioned projection) and
apply the same kill rule. Passing the legacy toy alone cannot satisfy the
DNA-native structural gate.

## Solver Bake-Off

On identical oracle pairs and Thought DNA, compare:

1. content TF-IDF/cosine baseline;
2. semantic-only Hungarian assignment;
3. role- and relation-aware WL/SME-lite baseline;
4. typed QAP hybrid with exact rescore;
5. partial FGW and C3-style multi-relational FGW-CG (one matrix per relation
   type plus transpose) with the identical exact rescore; and
6. exact/timed GED only for tiny diagnostic cases.

Record candidate pruning, restarts, all parameters, dependency versions, CPU,
wall time, peak memory, and configuration hash. The QAP/pFGW comparison changes
an ADR only after the frozen gate result, not through post-hoc tuning. Every
seeded solver runs at least one unseeded restart. Run both uniform and capped
relation-pattern-rarity weighting, and report the noisy-analogue versus
generic-chain margin rather than only aggregate AUC.

At least one family-12 case must test the representation boundary around
higher-order binding. If reviewers judge two source thoughts different while
Thought DNA v0.1 compiles them to the same binary graph, record a representation
collision and trigger schema reconsideration; do not pretend a solver can
recover information absent from its input.

## Scale Replay

The 136-graph suite cannot establish million-corpus scale. Replay fixed queries
against `10^3`, `10^4`, `10^5`, then `10^6` synthetic nonrelevant IDs while
preserving a measured or explicitly synthetic feature-frequency distribution.
Report:

- build time and index bytes;
- median, p95, and maximum posting-list length;
- postings touched and skipped evidence per query;
- p50/p95 query latency;
- Recall@5/20; and
- peak memory.

Run both E1 filler worlds at every feasible scale and add a third distribution
derived from actual extracted fixtures once available. The two synthetic worlds
bracket hypotheses; they do not establish the real motif distribution.

Do not claim scale if synthetic distractors are uniformly distributed while the
real system expects a Zipfian motif tail.

## Freeze and Change Policy

1. Author and validate all fixtures.
2. Obtain second-human approval for manual analogical, intent, generic-motif,
   and complementary judgments.
3. Publish the pack manifest hash.
4. Freeze candidate config/commit using calibration packs only.
5. Run gate packs once and retain every failure artifact.
6. Fixes create a new candidate config; changed cases create Benchmark v0.2.
7. Never rewrite v0.1 gold to make the current algorithm pass.

## Known Validity Risks

- Authored analogies may encode the architecture author's theory.
- Transform generators may leak family-specific artifacts.
- Symmetric structures may make one gold mapping arbitrary.
- Synthetic extraction errors may be cleaner than real model errors.
- Public cases can be overfit after the first run.
- Calibration and gate domains may still be too small to generalize.
- A small suite cannot measure real corpus motif skew.

These are reasons to preserve provenance, independent review, and future
versions—not reasons to replace the gate with an unreviewed aggregate.

## Related Documents

- [R0 Synthesis](../research/reviews/R0_SYNTHESIS_parshkov-openai-gpt5-codex-s7d3.md)
- [Thought DNA v0.1](../docs/THOUGHT_DNA_v0.1.md)
- [Invariance Specification](../docs/INVARIANCE_SPECIFICATION_v0.1.md)
- [Retrieval ADR](../docs/decisions/ADR-0002-retrieval-candidate-generation.md)
- [Verification ADR](../docs/decisions/ADR-0003-structural-verification.md)
- [Scoring Contract](../docs/RESONANCE_SCORING_v0.1.md)
