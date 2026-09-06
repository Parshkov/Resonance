# Typed Partial Graph Alignment for Structural Verification

Status: accepted for engine 0.1; partially superseded by ADR-0004 (engine 0.2): see that record for the retrieval stop-key rule, the concept channel and the classification policy.

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

Post-submit PR #37 ran those proposal families on one shared discrete scorer.
C1-style RRWM (no semantic `top_d`) and C3 multi-rel FGW both passed the
combined analogical/hard-negative gate; C2-style single shortest-path FGW did
not; C1-style semantic `top_d=3` deleted the analogical case. That bake-off is
a prototype-default result, not a production freeze: the RRWM was not
pygmtools, the node similarity was a stipulated oracle, and the graphs were
tiny.

## Decision

Adopt a common proposal/consistency/round/adjudicate pipeline. The v0.1
**prototype default** is multi-relational FGW-CG. Typed QAP/RRWM remains a
**co-equal gate candidate / fallback**. Production primary is selected only by
the frozen DNA-native lexicographic rule below, not by the PR #37 toy.

```text
canonical graphs + optional retrieval seeds
  -> all node pairs, or a structural/role-soft mask that is NOT a semantic top-d
  -> canonical and guarded coarse views
  -> typed-directed soft proposal
       default prototype: multi-relational FGW-CG
         (one matrix per relation type + transpose, α≈0.7 on the PR #37 testbed)
       co-equal fallback: sparse Lawler-QAP / RRWM, no semantic top-d
  -> parallel-connectivity / structural-consistency filter
  -> partial Hungarian assignment with explicit unmatched options
  -> exact add/drop/swap local improvement and structural rescore
  -> mapping, matched relations/paths, unmatched items, contradictions, scores
```

Semantic support MAY weight a proposal. It MUST NOT gate candidate node pairs
by semantic top-d / top-k shortlisting. C1's own failure mode 2, C3's
analogical semantic floor, and PR #37 (`S_struct` 1.000 → 0.024 at `top_d=3`)
make that shortcut a v0.1 NO-GO. Retrieval may still return a top-K list of
*graphs*. Functional-role compatibility MAY enter as a score component
(`N_role`); it MUST NOT be an exclusive pair mask until a DNA-native
experiment shows it does not recreate the semantic-pruning kill.

QAP association variables are candidate node pairs and its pairwise affinity
rewards preserved typed propositions. Multi-relational FGW uses one directed
adjacency/cost matrix per relation type and a separate transpose channel; a
single scalar, symmetrized, or shortest-path structure matrix is prohibited as
the primary encoding. Reversed direction, incompatible relation type,
assertion, or modality receives no compatibility credit.

The exact adjudicator is the polarity boundary for the entire pipeline. A
high-confidence mapped `causes`/`prevents`, asserted/negated, or directed-sign
conflict invalidates that correspondence and prevents a direct/analogical
acceptance unless a different conflict-free mapping passes. This is a hard
decision rule, not merely a small negative weight: E1 shows structural retrieval
can rank a one-edge polarity flip above a true noisy analogue.

The final adjudicator evaluates the discrete mapping with the
[Scoring Contract](../RESONANCE_SCORING_v0.1.md), including signed
contradictions. RRWM's non-negative relaxation is a proposal mechanism, never
the final truth value.

### Solver-selection rule

Implement the smallest reproducible multi-relational FGW-CG **and** QAP-RRWM
proposals behind one interface. Partial/semi-relaxed FGW or epsilon padding are
declared unmatched-node variants of the FGW family, not separate final scorers.
Every coupling or soft assignment is filtered, rounded to a partial injective
mapping, and passed through the identical exact adjudicator. A relaxation
objective is never the final resonance decision.

v0.1 ships FGW-CG as the prototype default because PR #37 measured higher
noisy-positive recall (0.740 vs 0.375) and reproduced C3's table on the shared
scorer, and because C2+C3 already sat in the FGW family once encoding is typed
and directed. This inverts C1's paper ranking only for the prototype. It is
not a production crown: the measured RRWM is not pygmtools.

Among candidates that pass every mandatory DNA-native gate, select production
primary lexicographically by: hard-negative top-1/SOW, automorphism-tolerant
mapping F1, worst-family recall, then p95 latency and implementation
complexity. If neither passes, keep SME-lite as the diagnostic baseline and
revise representation or extraction; do not choose the less-bad relaxation.

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
- R0-C2 provides the strongest alternative for partial/noisy overlap but left
  directed typed graph costs as its main uncertainty and executed no code.
  PR #37 resolved that uncertainty against a single shortest-path matrix.
- R0-C3 resolves the encoding hypothesis in a small executed experiment using
  per-relation matrices plus transposes, while exposing generic-motif margin,
  seed, non-convexity, and cross-size normalization risks.
- All three converge on partial mapping, consistency, discrete typed rescore,
  separate components, and exact GED/MCS rejection.
- R0-A supplies the structural constraints and systematicity rationale.
- R0-D supplies the only semantically guarded granularity mechanism.
- R0-G supplies correspondence, hard-negative, runtime, and stage-isolation
  metrics.
- R0-B E1 shows why retrieval-side redundancy cannot be trusted for polarity;
  the verifier must reject the surfaced sign-inverted near-duplicate.
- R0-C-REVIEW2 / PR #37 executed the missing shared-testbed bake-off: typed
  QAP-RRWM and multi-rel FGW both pass 8/8; path-distance FGW fails analogical
  floors; semantic `top_d=3` is a kill switch for analogy; equal-weight blend
  inverts the project's hard negative. Remaining limits: stipulated oracle,
  tiny graphs, numpy RRWM ≠ pygmtools.

Exact artifacts and head SHAs are recorded in
[R0 Synthesis](../../research/reviews/R0_SYNTHESIS_parshkov-openai-gpt5-codex-s7d3.md).

## Alternatives Considered

### Leave the prototype solver unnamed after PR #37

Rejected as of this revision. A shared-testbed result now exists. Naming no
default would force every implementer to re-litigate C1 vs C3. The remaining
uncertainty is library/oracle/size, which is why QAP stays a co-equal gate
candidate rather than being deleted.

### Freeze production QAP or FGW from the PR #37 toy

Rejected. The bake-off used a stipulated similarity oracle and a numpy RRWM
that is not C1's pygmtools path. Production primary still requires the frozen
DNA-native lexicographic rule.

### Semantic top-d / top-k node-pair pruning

Rejected as a v0.1 candidate mask. C1 named this as failure mode 2; C3
measured analogical semantic support near 0.05; PR #37 measured `top_d=3`
dropping analogical `S_struct` from 1.000 to 0.024. Semantic weights may
exist; they may not delete analogical pairs before structure can rescue them.

### Single-matrix or shortest-path FGW as primary encoding

Rejected. C2 left this as its main uncertainty; PR #37 failed the analogical
struct/accuracy floors on that encoding (0.655 / 0.698). Per-type directed
matrices plus transpose, or native typed pairwise QAP terms, are the surviving
encodings.

### Blended-only public scoring API

Rejected. The scoring contract is a vector plus mapping. Equal-weight
`(S_struct + S_sem) / 2` inverts analog vs rewired on C3's winning numbers.
C1's structure-heavy weights would still separate that pair; that does not
license a blended-only API.

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
- Semantic top-d node-pair masks are prohibited. Dense unpruned 100×100 QAP is
  still a scaling NO-GO and must be solved by sparsity, typed structure, or
  FGW — not by semantic shortlisting. Verification processes a top-K list of
  graphs with a memory-aware concurrency cap.
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
- p95 verification time at most `2 s` per 50×50 pair after graph-level top-K
  (not semantic node-pair pruning) on the declared reference CPU;
- deterministic exact rescoring and mapping-set equivalence for fixed inputs;
  and
- every retrieved polarity-flip regression is rejected end-to-end even when it
  ranks above the true analogue during candidate retrieval.

The DNA-native bake-off includes semantic Hungarian and path-distance FGW as
**diagnostic controls expected to fail the analogical gate**; SME-lite greedy;
typed QAP hybrid with **no semantic top-d**; C3-style multi-relational FGW-CG
with identical rescore; and exact/timed GED only on tiny cases. Semantic
`top_d` pair-pruning is a required failing control, not a shipping
configuration. PR #37 is provenance for the prototype default; it does not
replace this frozen DNA-native run. It runs on one machine, includes seeded
and unseeded restarts, generic-motif rarity ablations, pygmtools RRWM if used,
and sweeps fragment/whole size ratios. Report score by family and do not
average away a polarity, reversal, or global-conflict failure.

## Known Failure Modes

1. Semantic candidate-pair pruning removes the true cross-domain node pair
   (v0.1 prohibition, not a tolerated risk).
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

- Changing the prototype default or the selected production solver requires
  recorded DNA-native benchmark evidence. A pygmtools replay of the PR #37
  harness that closes the noisy-recall gap may invert the prototype ranking.
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
