---
mission: R0-C
run: R0-C-REVIEW2
review_type: independent comparative review + shared-testbed bake-off
contributor: Parshkov
agent_id: parshkov-xai-grok46-k3e8
agent_or_model: Grok 4.6 (Grok Build TUI; exact mode not exposed)
date: 2026-08-31
mission_modified: false
web_research_used: false
code_execution_used: true
experiment: research/experiments/R0_C_REVIEW2_bakeoff.py
experiment_output: research/experiments/R0_C_REVIEW2_bakeoff_output.txt
blind_constraints_preserved: not-applicable
notes: >
  Non-exclusive review. Does not claim canonical R0-C1, R0-C2, or R0-SYNTHESIS.
  Conflict: this identity authored R0-E, R0-H, and R0-F; it did not author C1,
  C2, C3, or the existing C review. The existing C review invited a conflict-free
  independent repeat. This run did not open
  research/reviews/R0_C_structural_verifier_review_*.md. It did read the
  one-paragraph C-review summary posted on issue #13 at 2026-08-31T19:17:03Z
  (limited anchoring, disclosed). C1/C2/C3 submissions were read in full, as a
  comparative review requires. Issue comments also exposed B2/E1/H summaries;
  those were not used as C evidence.
---

# Scope

Independent comparative review of the three R0-C verifier reports, plus a
shared-testbed bake-off of the disagreement they actually leave behind.

The mission question is: given two Thought Graphs of roughly 10–100 nodes,
what practical verifier should return structurally analogous subgraphs, node
correspondences, and a score that can tell *different words, same structure*
from *same words, different structure*?

This is not a canonical C run and not a synthesis ADR. It is review input for
issue #13 / the R0-C pair (#6, #7).

# Inputs Reviewed

| Run | Agent | Family | Primary recommendation | Executed? |
|---|---|---|---|---|
| C1 (canonical) | parshkov-openai-gpt5-codex-c914 | GPT-5 Codex | Typed Lawler QAP, RRWM proposal, Hungarian + exact rescore; pFGW is fallback, not judge | 50-node pygmtools smoke test only |
| C2 (canonical) | julianadamsciv-blip-openai-gpt56sol-8f2c | GPT-5.6 Sol | Partial FGW → discrete mapping → typed directed-edge rescore; FAQ/QAP fallback | No |
| C3 (repeat) | dima2010-anthropic-opus5-f5ae | Claude Opus 5 | Multi-relational FGW (one matrix per relation type + transpose), ε-padding, SME-style consistency, Hungarian; spectral matching fallback | Yes, on its own 9-graph toy |

Sibling C1↔C2 blindness is over (both submitted). C3 disclosed it is not independent of B2 (same author). This review is independent of C1/C2/C3 authorship.

# Independent Convergence

Read side by side, the three reports already agree on the architecture *shape*
before any bake-off:

1. **Verification, not retrieval.** All three place the method after top-K. None
   propose running alignment over a 1M corpus.
2. **Hybrid, not one algorithm.** Soft proposal → one-to-one / consistency
   pressure → discrete injective mapping → typed-edge rescore. C1 writes it as
   `candidate pairs → RRWM → partial Hungarian → exact J`. C2 as
   `pFGW coupling → Hungarian on −T → directed-edge rescore`. C3 as
   `FGW π → SME-style filter → Hungarian`. Mission question 2 is answered yes
   independently three times.
3. **Correspondences, not a scalar.** The output contract is a partial mapping
   plus unmatched nodes plus component scores. A GW/QAP objective value is not
   the Resonance score.
4. **Directed typed property (multi)graph.** Trees are too weak; hypergraphs are
   not justified for MVP. Direction and relation type are first-class because
   reversal and type substitution are hard negatives.
5. **Unmatched nodes are first-class.** Dummy/ε-padding (C1, C3) or partial
   transported mass (C2). Full-mass matching is the wrong default.
6. **Reject as primary:** exact GED, MCS, subgraph isomorphism, whole-graph
   cosine, and any newly trained GNN matcher. The reasons coincide: NP-hard
   brittleness, no graded cross-domain score, or a violation of the no-new-model
   constraint.
7. **Granularity is not a verifier hyperparameter.** C1 says invariance F is
   unsupported under 1–1 node maps. C3 hands it to R0-D. C2 claims only partial
   path-distance tolerance. None of them try to buy `A→B` vs `A→X→Y→B` with an
   edit-cost trick.

That is already enough to write a verification ADR *skeleton*. It is not enough
to freeze a solver.

# Material Disagreements

## D1. Primary solver family (the live architecture fork)

- C1: **QAP/RRWM is the judge**; pFGW may propose when the QAP is unstable.
- C2: **pFGW is the judge**; FAQ/QAP is the fallback for near-equal sizes.
- C3: **multi-relational FGW is the judge**; spectral matching is the fallback.

C1 and C2 are the blind pair and they disagree. C3, from a third model family,
sides with C2's *family* (fused GW) while rewriting C2's structural encoding.

## D2. How to encode a directed typed Thought Graph as "structure"

C2's own main uncertainty is the whole disagreement: vanilla FGW was built for
one structural cost matrix. Thought Graphs have typed, directed, signed edges.

C3's answer: one adjacency per relation type **and its transpose**, summed in
the quadratic term. Cost is `|R|` times a still-cheap `O(mn²+m²n)` iteration.

C1 never collapses to a matrix: pairwise QAP terms fire on directed typed
multiedges, and reversed direction scores zero.

C2 leaves "one or more" matrices and a symmetrized baseline as an experiment.

## D3. What the verifier consumes besides edges

C1 and C2 require a compact **functional node role** plus a semantic handle.
C3 says the verifier needs a node-pair **similarity function**, not roles, not
ontology URIs, and not reification. C3 also treats B2's seed-handoff as a
hypothesis and measures that seeds buy determinism, not correspondence
accuracy.

## D4. Scalar blend vs score vector

C1 and C2 emit a weighted scalar (`0.25 N + 0.55 R + …` / `0.25 N + 0.50 R +
…`). C3 refuses to blend: report `(S_struct, S_sem, cover, κ)` and classify from
the quadrant. C3's reason is that a mid blend makes the project's hard negative
unattributable.

## D5. Evidence status

Only C3 executed the mission's toy experiment. C1 ran a same-domain permutation
smoke test (runtime, not accuracy). C2 is argument-only. An unexecuted
disagreement between C1 and C2 is not yet an empirical result.

# Assumption Matrix

| Assumption | C1 | C2 | C3 | Status after bake-off |
|---|---|---|---|---|
| Hybrid pipeline | yes | yes | yes | unchallenged |
| Typed directed edges required | yes | yes | yes | confirmed: type-swap and reversal move the score |
| Node roles required at verify time | yes | yes | no | not required for the analogical recovery measured here |
| Semantic candidate pruning is safe | proposed `top_d` | n/a | no | **falsified** (`top_d=3` kills cross-domain) |
| One shortest-path matrix is enough structure | no (QAP) | maybe (the open question) | no | **falsified** as a primary encoding |
| Per-type + transpose is enough structure | n/a (native pairwise) | "or more" | yes | sufficient on this toy |
| Seeds from retrieval improve accuracy | desired | optional | measured no | not re-tested here; C3's table stands |
| A blended scalar is a safe API | yes | yes | no | **unsafe at equal weights**; C1/C2's structure-heavy weights would still separate the headline pair |
| Granularity invariance in the 1–1 verifier | no | partial | hand to R0-D | **unsupported** by every method tested |
| 50×50 top-20 is computationally easy | ~9 s pygmtools dense; prune or NO-GO at 100 | sub-second–seconds, grid multiplies | 8.7 ms / 0.17 s | all three families are feasible at 50×50; dense unpruned QAP is the scaling risk |

# Experiment

Designed from C1/C2/C3's own toy experiments and kill language, **not** from the
prior review's E-C1 spec (unread). Shared discrete scorer; only the proposal
generator varies.

- Testbed: C3's graphs (cited) plus C1's extra negatives — causal reversal,
  `causes↔prevents` swap, and a main-chain granularity split.
- Methods: semantic Hungarian; C1-style RRWM-adjacent QAP on all pairs; the
  same QAP with `top_d=3` semantic pruning; C2-style FGW on one undirected
  shortest-path matrix (`α=0.7`); C3 multi-rel FGW at `α=0` and `α=0.7`.
- Solver notes: FGW is the same Peyré/Vayer conditional-gradient construction
  C3 used (numpy/scipy, no POT). RRWM is association-graph power iteration plus
  Sinkhorn 1–1 reweighting, **not** bit-exact pygmtools. A previous unmatched-
  cost calibration emptied every mapping; that bug is not evidence against C1
  and was not used. Empty mappings after the dummy-pad mistake were discarded.
- 12 random relabelings per case. numpy 2.5.2 / scipy 1.18.1.

Full tables: `research/experiments/R0_C_REVIEW2_bakeoff_output.txt`.

Headline `S_struct` (mean):

| method | cross-domain | noisy analog | rewired | generic long | reversal | type-swap | granularity |
|---|---:|---:|---:|---:|---:|---:|---:|
| SEM-Hungarian | 0.083 | 0.052 | 0.143 | 0.107 | 0.000 | 0.286 | 0.400 |
| C1-RRWM-all | **1.000** | 0.375 | 0.143 | 0.143 | 0.143 | 0.143 | 0.400 |
| C1-RRWM-sem3 | 0.024 | 0.021 | 0.143 | 0.036 | 0.143 | 0.310 | 0.392 |
| C2-FGW-path | 0.655 | 0.240 | 0.143 | 0.155 | 0.000 | 0.286 | 0.300 |
| C3-FGW-multi `α=0` | 0.083 | 0.052 | 0.143 | 0.107 | 0.000 | 0.286 | 0.400 |
| C3-FGW-multi `α=0.7` | **1.000** | **0.740** | 0.143 | 0.512 | 0.000 | 0.571 | 0.400 |

Kill rules drawn from C1/C2/C3 (8 checks: paraphrase, cross-domain struct,
cross-domain accuracy, rewired gap, noisy>generic, reversal, type-swap,
cross-domain semantics stay low):

| method | passed |
|---|---|
| SEM-Hungarian | 2/8 |
| C1-RRWM-all | **8/8** |
| C1-RRWM-sem3 | 2/8 |
| C2-FGW-path `α=0.7` | 6/8 (fails cross-domain struct≥0.8 and acc≥0.8) |
| C3-FGW-multi `α=0` | 2/8 (identical to SEM — the structure term is doing the work) |
| C3-FGW-multi `α=0.7` | **8/8** |

C3 `α=0.7` **reproduces C3's published table** on the shared cases (cross-domain
1.000/acc 1.000, noisy 0.740, generic-long 0.512, rewired 0.143, partial 0.393).
That is a successful mechanical reproduction, not a new claim.

50×50 one-pair runtime on this machine: SEM 0.7 ms, C2-path 6.8 ms, C3-multi
13.4 ms, C1-RRWM 52 ms. Top-20 is 0.01–1.0 s. Verification is not the bottleneck
at MVP size. C1's dense-`K` warning at 100×100 is still in force for unpruned
QAP (`p=n²`).

## What the numbers actually decide

**Semantic-only matching cannot do the analogical case.** Cross-domain
`S_struct=0.083`, accuracy 0.156. C3 already measured this; it replicates under
a shared scorer.

**Semantic candidate pruning is a kill switch for analogy.** C1 listed this as
failure mode 2. Measured: `top_d=3` drops cross-domain `S_struct` from 1.000 to
0.024, because every analog node has `sim=0.05` and the true pair is not in the
shortlist. If retrieval hands the verifier a semantic top-d, it can delete the
case Resonance exists to find. Role-based gates were not tested; semantic
top-d is.

**C2's stated uncertainty is resolved against the single-matrix baseline.**
Path-distance FGW at `α=0.7` reaches only 0.655 struct / 0.698 accuracy on the
clean analog, and 0.240 on the noisy analog. The FGW *family* is not the
failure; collapsing type and direction into one hop-distance matrix is.

**Typed QAP and multi-rel FGW both pass the combined gate.** They do not have
the same error profile:

- C3-multi has much higher noisy-positive recall (0.740 vs 0.375).
- C1-RRWM rejects generic long chains and type-swaps more aggressively
  (0.143 / 0.143 vs 0.512 / 0.571).
- C3-multi on reversal is the clean vector reject: identity mapping,
  `S_sem=1.000`, `S_struct=0.000` (same words, reversed structure).
- Type-swap is C3's thin spot: `increases` edges survive `causes↔prevents`, so
  `S_struct=0.571`. The gate still passes (`0.571 ≤ 1.000−0.3`) but not
  comfortably.
- The noisy-vs-generic *margin* is almost identical (~0.23) for both passing
  methods. C3's own warning stands: unweighted structural agreement is a
  mediocre decision statistic on generic chains. C3 recommended `idf` on
  relational patterns; this bake-off did not implement it.

**A 50/50 blend of `S_struct` and `S_sem` fails the project's hard negative
on C3's own winning numbers:** analog `0.5·1.000+0.5·0.050=0.525`, rewired
`0.5·0.143+0.5·1.000=0.572`. The hard negative wins. C1's proposed weights
(`0.25 N + 0.55 R + 0.20 Q`) would still rank analog 0.763 above rewired 0.529,
so this does not falsify C1's particular blend. It does falsify "any blend is
fine" and it supports C3's API: **always emit the vector; if a scalar is
needed, structure must dominate, and the quadrant table remains the
explanation.**

**Granularity is an expected failure, 0.30–0.40, every method.** Do not tune
the 1–1 verifier to pass it. That is R0-D's problem.

**Node roles were not required** for C1-RRWM-all or C3-multi to recover the
clean analog. Both used typed edges plus a weak stipulated similarity oracle
(`1.0 / 0.85 / 0.05`). C3's "similarity function, not an ontology" is the
weaker Thought-DNA demand that the analogical case actually used.

# Experiments Needed

This bake-off is still a 4–11 node stipulated-oracle toy. It does **not** close:

1. **A larger typed-QAP vs multi-rel FGW vs path-FGW head-to-head** on C1's
   proposed 12-node motif suite (200 pairs, vocabulary substitution, 30%
   junk, 20% deletion, reversal, type-incompatibility). This numpy RRWM is
   not pygmtools; C1's actual solver could close the noisy-recall gap.
2. **A real encoder instead of the 1.00/0.85/0.05 oracle.** C3 named this as
   the largest reality gap. α's safe range will shrink.
3. **Cross-size score normalisation.** Partial fragments score 0.29–0.39
   against an 8-node parent because `S_struct` divides by `max(|E1|,|E2|)`.
   No global threshold should ship until this is fixed (C3 consequence 7).
4. **idf (or other rarity) on relational patterns**, which is C3's proposed
   fix for generic-chain collapse. Not implemented here.
5. **C3's seeding result** (accuracy falls as true seeds are added) should be
   reproduced by a different implementation before retrieval is told to emit
   seeds as an accuracy feature.

None of those block a verification *prototype*. They block a frozen production
matcher and a single global threshold.

# Consequences for Thought DNA

1. Persist **directed, typed, signed** edges. Type and direction are the
   analogical signal once entity vocabulary is discounted.
2. Persist a **node-pair similarity function** (embedding cosine, Knowledge-DNA
   handle, or bucketed concept id). The verifier does not need the internals.
3. **Do not make functional roles a verify-time hard gate** until someone shows
   they help *without* recreating the semantic-pruning kill. Roles may still be
   useful for extraction and for human explanation.
4. **Do not reify** for MVP verification. C3's quadratic term already couples
   two-step paths; C1 would compile a hyperedge to an event node if needed.
5. Extraction confidence is optional weighting, not a matching key.
6. Matching API: partial injective map, unmatched nodes, matched typed edges,
   **score vector** `(struct, sem, cover, systematicity)`, top contradictions.
7. Retrieval must not prune analogical candidates by semantic top-d. If it
   emits seeds, treat them as a restart, not as the only basin.
8. Granularity belongs in a separate layer (R0-D), not in edit costs.
9. Benchmark families that this review now treats as mandatory: clean
   cross-domain; noisy D+E+I analog; same-words rewire; generic long chain;
   causal reversal; relation-type swap; granularity as a *control failure*.

# Recommended Architecture Decision

**GO for a three-stage verifier. QUALIFIED GO on the solver. NO-GO on three
tempting shortcuts.**

- **Pipeline (HIGH confidence):** soft proposal → discrete injective partial
  map → exact typed-edge rescore, emitting a vector plus the mapping. This is
  3/3 independent text plus the bake-off.
- **Structural encoding (HIGH confidence):** per-relation-type directed
  structure, with reverse direction as a distinct channel. C2's open question
  is answered: a single symmetrized shortest-path matrix is not enough to
  pass the analogical gate. C3's encoding and C1's native pairwise typed
  terms are the two surviving ways to say the same thing.
- **Default prototype solver (MEDIUM confidence):** C3 multi-relational FGW
  at `α ≈ 0.7` (C3 measured a usable range `α ≥ 0.3` on the clean analog).
  Reasons to default here rather than declare a unique winner: (i) noisy-
  positive recall 0.740 vs 0.375 on this testbed, (ii) mechanical reproduction
  of C3's table, (iii) 4× faster than this RRWM at 50×50, (iv) C2 and C3, two
  of three runs including the blind C2, are in the FGW family once encoding
  is fixed. **This is a prototype default, not a production freeze.**
- **Co-equal gate candidate / fallback (MEDIUM):** typed QAP/RRWM as C1
  specified, with **no semantic top-d pruning**. Keep it in the same bake-off
  harness. Invert C1's ranking only for the v0.1 prototype: FGW-family
  default, QAP fallback — the opposite of C1's paper ranking, justified by
  C2+C3 agreement and noisy recall, qualified by "this RRWM ≠ pygmtools".
- **NO-GO:** vanilla single-matrix FGW as the primary encoding; semantic
  candidate pruning; blended-only APIs; exact GED/MCS/VF2 as the 50-node
  default; GNN matchers; claiming granularity invariance in this layer.

C2 is not "wrong." C2 recommended pFGW and then named the encoding problem
that C3 solved. The surviving FGW design is C2's method with C3's matrices.

# Confidence

**HIGH** on the pipeline, the typed/directed encoding, the no-semantic-prune
rule, the vector API, and the rejection of GED/GNN/cosine.

**MEDIUM** on naming multi-rel FGW as the v0.1 default rather than leaving
C1 and C3 permanently co-equal. Main uncertainty: stipulated oracle, 8-node
graphs, and a numpy RRWM that is not C1's library. A pygmtools re-run of the
same harness could flip the noisy-recall comparison.

**LOW** on any global numeric threshold. Partial-vs-full `S_struct` is not
comparable; generic-chain `0.512` vs noisy analog `0.740` is too thin to ship.

# Open Questions

1. Does pygmtools RRWM recover C3-like noisy recall on this exact testbed?
2. Does `idf` on relation (or path) patterns lift C3's generic-chain problem
   without flattening true analogies?
3. What replaces `max(|E1|,|E2|)` so a 4-node fragment and an 8-node parent
   can share a threshold?
4. How does a real R0-E/R0-F similarity function change the safe `α` interval?
5. Should retrieval emit seeds at all, given C3's accuracy-vs-determinism
   measurement?

# Sources

Primary inputs are the three submissions. Algorithmic claims inherit their
citations; this review did not add a new literature pass.

1. C1 submission, `research/submissions/R0_C1_alignment_parshkov-openai-gpt5-codex-c914.md` — QAP/RRWM hybrid, failure mode 2 (semantic pruning), granularity as unsupported, pygmtools smoke-test cost.
2. C2 submission, `research/submissions/R0_C2_alignment_julianadamsciv-blip-openai-gpt56sol-8f2c.md` — pFGW primary; explicitly flags directed/typed matrix encoding as the main uncertainty.
3. C3 submission, `research/submissions/R0_C3_alignment_dima2010-anthropic-opus5-f5ae.md` plus `research/experiments/R0_C3_alignment_experiment.py` — multi-rel FGW, executed table reproduced here, unblended vector, generic-chain warning, seed result.
4. Vayer et al., ICML 2019, "Optimal Transport for structured data with application on graphs" — FGW objective and `α` trade-off used by C2/C3 and by this bake-off.
5. Peyré, Cuturi & Solomon, ICML 2016, "Gromov-Wasserstein Averaging of Kernel and Distance Matrices" — square-loss tensor that makes the CG iteration cheap.
6. Cho, Lee & Lee, ECCV 2010, "Reweighted Random Walks for Graph Matching" — C1's proposal generator; this implementation is adjacent, not a port.
7. Falkenhainer, Forbus & Gentner, 1989, Structure-Mapping Engine — source of the systematicity/consistency stage all three hybrids borrow.
8. This run's artifact: `research/experiments/R0_C_REVIEW2_bakeoff.py` / `_output.txt`.
