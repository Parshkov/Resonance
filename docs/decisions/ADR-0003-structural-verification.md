# Typed Partial Graph Alignment for Structural Verification

Status: proposed

Date: 2026-08-31

## Context

The verifier receives about 20 candidate Thought Graphs and must distinguish
relational correspondence from lexical/topic overlap. It must tolerate unequal
sizes and missing/irrelevant branches, preserve direction/type/polarity, return
an inspectable partial mapping, and remain practical for roughly 10–100 nodes.

The blind R0-C runs select different soft proposal optimizers. C1 recommends a
typed Lawler QAP solved by RRWM; C2 recommends partial Fused
Gromov-Wasserstein. The independent C3 repeat executed a multi-relational FGW
with one matrix per relation type plus its transpose. All require consistency,
partial Hungarian rounding, and typed directed-edge rescoring. R0-A adds
one-to-one correspondence, parallel connectivity, and systematicity. R0-D shows
that granularity must be handled by guarded reversible views and bounded
edge-to-path matching, not arbitrary edit costs.

## Decision

Adopt a common proposal/consistency/round/adjudicate pipeline, and leave the
production proposal solver to the frozen head-to-head defined below:

```text
canonical graphs + optional retrieval seeds
  -> compatible candidate node pairs
  -> canonical and guarded coarse views
  -> typed-directed soft proposal
       A: sparse Lawler-QAP / RRWM
       B: multi-relational FGW-CG (one matrix per relation type + transpose)
  -> parallel-connectivity / structural-consistency filter
  -> partial Hungarian assignment with explicit unmatched options
  -> exact add/drop/swap local improvement and structural rescore
  -> mapping, matched relations/paths, unmatched items, contradictions, scores
```

Both proposals consume the same functional-role compatibility, optional
semantic support, extraction confidence, and versioned relation-compatibility
policy. QAP association variables are candidate node pairs and its pairwise
affinity rewards preserved typed propositions. Multi-relational FGW uses one
directed adjacency/cost matrix per relation type and a separate transpose
channel; a single scalar or symmetrized structure matrix is prohibited.
Reversed direction, incompatible relation type, assertion, or modality receives
no compatibility credit.

The final adjudicator evaluates the discrete mapping with the
[Scoring Contract](../RESONANCE_SCORING_v0.1.md), including signed
contradictions. RRWM's non-negative relaxation is a proposal mechanism, never
the final truth value.

### Solver-selection rule

Implement the smallest reproducible QAP-RRWM and multi-relational FGW-CG
proposals behind one interface. Partial/semi-relaxed FGW or epsilon padding are
declared unmatched-node variants, not separate final scorers. Every coupling or
soft assignment is filtered, rounded to a partial injective mapping, and passed
through the identical exact adjudicator. A relaxation objective is never the
final resonance decision.

Among candidates that pass every mandatory gate, select production primary
lexicographically by: hard-negative top-1/SOW, automorphism-tolerant mapping F1,
worst-family recall, then p95 latency and implementation complexity. If neither
passes, keep SME-lite as the diagnostic baseline and revise representation or
extraction; do not choose the less-bad relaxation.

When retrieval seeds initialize a solver, run at least one unseeded restart.
C3 measured that seeds reduced mapping variance to zero while lowering its
stipulated correspondence accuracy from 0.896 to 0.750. Seeds are hints for
latency/stability, not constraints or accuracy evidence.

### Systematicity and multiscale behavior

The adjudicator groups preserved propositions into connected mapped systems.
Connected evidence receives the explicit `Y_systematicity` component; isolated
generic relations cannot earn the same credit.

For a guarded transparent subdivision, a canonical relation may match a bounded
path of length at most four in the other graph. Every match expands to original
node/relation IDs. Unknown relation composition, meaningful intermediates,
polarity, assertion, direction, or modality differences reject the path match.

## Evidence

- R0-C1 executed a 50×50 typed RRWM/Hungarian smoke test and obtained practical
  runtime, while identifying dense 100×100 affinity as a NO-GO.
- R0-C2 provides the strongest alternative for partial/noisy overlap but notes
  that directed typed graph costs are unresolved and no code was executed.
- R0-C3 resolves the encoding hypothesis in a small executed experiment using
  per-relation matrices plus transposes, while exposing generic-motif margin,
  seed, non-convexity, and cross-size normalization risks.
- All three converge on partial mapping, consistency, discrete typed rescore,
  separate components, and exact GED/MCS rejection.
- R0-A supplies the structural constraints and systematicity rationale.
- R0-D supplies the only semantically guarded granularity mechanism.
- R0-G supplies correspondence, hard-negative, runtime, and stage-isolation
  metrics.

Exact artifacts and head SHAs are recorded in
[R0 Synthesis](../../research/reviews/R0_SYNTHESIS_parshkov-openai-gpt5-codex-s7d3.md).

## Alternatives Considered

### Preselect QAP or FGW from design arguments alone

Rejected. C1 and C3 executed different datasets on different machines; C2 did
not execute. QAP represents candidate affinities directly, while FGW handles
soft partial structure naturally. Neither evidence base supports a production
crown before identical exact rescoring on one frozen benchmark.

### Pure SME-lite greedy kernels

Retained as a transparent baseline. It may become the production choice if it
matches QAP accuracy with lower complexity, but it does not currently provide
the same general affinity optimization.

### Semantic Hungarian assignment

Baseline only. It cannot distinguish same words with different relations.

### Exact GED, MCS, VF2, A*, or exact QAP

Rejected as the 50-node default because of combinatorial cost and opaque/edit
weight sensitivity. They may act as tiny-graph oracles.

### Whole-graph embedding or LLM judge

Rejected because they do not yield deterministic relational correspondence and
violate the project's comparison constraints.

## Consequences

- Thought DNA preserves stable IDs, functional roles, typed directed parallel
  relations, relation identity, confidence, assertion/modality, and provenance.
- Candidate masks/feature costs must be recorded; retrieval seeds are hints,
  never hard truth, and cannot replace an unseeded restart.
- Dense unpruned 100×100 QAP is prohibited. Verification processes top-K with a
  memory-aware concurrency cap.
- “Unmatched” is explicit in optimization and output.
- Structural and semantic signals remain separate. The final mapping and exact
  scorer, not a relaxation objective, define the result.
- Granularity support is conditional and provenance-preserving.
- Solver restarts, initializations, candidate truncation, transported-mass or
  padding policy, and alternative mappings are recorded for reproducibility.

## Benchmark / Validation

Freeze solver configuration before gate execution. Report both oracle-retrieval
verification and end-to-end retrieval+verification.

Mandatory verifier gates:

- SOW at least `10/12`, ties fail;
- overall gate Recall@5 at least `0.85` under oracle candidate inclusion;
- each positive family Recall@5 at least `4/6`;
- resonance precision at least `0.80`;
- overall negative FPR at most `0.10`, and no negative family above `1/6`;
- node-pair F1 at least `0.70`, with automorphism-tolerant alternatives;
- directed typed edge preservation at least `0.75`;
- zero false contractions of marked meaningful nodes;
- p95 verification time at most `2 s` per 50×50 pair after candidate pruning on
  the declared reference CPU; and
- deterministic exact rescoring and mapping-set equivalence for fixed inputs.

The bake-off includes semantic Hungarian, SME-lite greedy, QAP hybrid,
partial/multi-relational FGW-CG with identical rescore, and exact/timed GED only
on tiny cases. It runs on one machine, includes seeded and unseeded restarts,
generic-motif rarity ablations, and sweeps fragment/whole size ratios. Report
score by family and do not average away a polarity, reversal, or global-conflict
failure.

## Known Failure Modes

1. Candidate pruning removes the true cross-domain node pair.
2. Symmetric/automorphic motifs admit several valid mappings.
3. Generic hubs dominate unary and pairwise rewards.
4. Relation compatibility that is too broad creates false causal analogies.
5. QAP or FGW relaxation/local search settles in unstable local optima.
6. Dense candidate affinity exhausts memory.
7. pFGW structural costs erase direction/type or choose arbitrary mass.
8. A high-confidence extraction error gains systematicity credit.
9. Tiny common motifs score perfectly without the evidence gate.
10. Unsafe chain contraction erases a meaningful mechanism.

## Conditions for Reconsideration

- Select QAP or FGW only through the declared frozen lexicographic rule; changing
  the selected production solver afterward requires recorded benchmark evidence.
- Prefer SME-lite if it reaches the same family-level gates with materially less
  latency/complexity.
- Revisit Thought DNA if repeated failures require grounded relation-as-argument
  structure absent from v0.1.
- Revisit the verifier rather than increasing semantic weight if same-word
  rewired negatives outrank cross-domain structural positives.
- Stop matcher work and repair extraction if duplicate-extract self-match fails.

## Related Research

- [R0 Synthesis](../../research/reviews/R0_SYNTHESIS_parshkov-openai-gpt5-codex-s7d3.md)
- [Thought DNA v0.1](../THOUGHT_DNA_v0.1.md)
- [Invariance Specification](../INVARIANCE_SPECIFICATION_v0.1.md)
- [Benchmark v0.1](../../benchmark/R0_BENCHMARK_v0.1.md)
