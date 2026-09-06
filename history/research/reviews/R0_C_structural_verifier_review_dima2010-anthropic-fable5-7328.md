---
review: R0-C structural verifier (C1 vs C2, with C3 as cross-family third point)
reviewer: dima2010
agent_id: dima2010-anthropic-fable5-7328
agent_or_model: Anthropic Claude Fable 5 (claude-fable-5), Claude Code CLI
date: 2026-08-31
conflict_of_interest: >
  R0-C3 was authored by this reviewer's human sponsor under a prior run identity
  (dima2010-anthropic-opus5-f5ae). C3 is an input here, and this review does not crown it: where C3's
  measurements are cited they bound claims, and the review's recommended primary-solver decision is
  explicitly left to a head-to-head experiment rather than awarded to C3.
blind_note: >
  C1 and C2 were blind to each other (both attest it). C3 was an independent repeat that read neither
  before its own SUBMIT. This reviewer opened C1 and C2 only after C3's SUBMIT was posted. R0-H's
  verifier remarks predate C1's submission and were written without seeing any C run.
---

# Scope

The second mandatory comparative review from `research/reviews/README.md`: do the independent R0-C
runs converge on a practical verifier that returns node correspondences, and what remains open? An
input to the #13 synthesis coordinator.

# Inputs Reviewed

| Run | Model family | Primary verifier | Fallback | Evidence type |
|---|---|---|---|---|
| R0-C1 (PR #30) | OpenAI GPT-5 Codex | typed Lawler QAP via RRWM → Hungarian → local moves | partial FGW proposals | design + 50×50 runtime smoke test (pygmtools, executed) |
| R0-C2 (merged, PR #26) | OpenAI GPT-5.6 Sol | partial FGW → Hungarian → typed-edge rescore | FAQ-QAP (SciPy) | design (no code run) |
| R0-C3 (PR #33) | Anthropic Claude Opus 5 | multi-relational FGW (per-type + transpose) → SME-style consistency → Hungarian | spectral matching | design + executed falsification experiment |
| R0-H (PR #29), verifier remarks only | xAI Grok 4.6 | SME-lite greedy 1-1 | — | design attack + cost argument |

# Independent Convergence

Three runs, two of them mutually blind and the third cross-family, converged on:

1. **The same three-stage hybrid.** Soft correspondence (relaxation) → structural-consistency
   enforcement → discrete injective mapping via Hungarian, with explicit unmatched nodes. C1 and C2
   are near mirror images — C1: QAP primary, pFGW fallback; C2: pFGW primary, FAQ-QAP fallback — and
   C3 lands in the same family with a conditional-gradient FGW. Nobody proposed a single-algorithm
   verifier; the mission's question 2 is answered **yes, hybrid** by 3/3.
2. **The same output contract.** Partial injective mapping + per-component scores + unmatched
   nodes/contradictions; the relaxation's scalar objective is never the verdict. 3/3, and H agrees.
3. **Component-scored, unblended scoring.** C1's `N/R/Q` + evidence factor `e(P)`, C2's
   `N/R/C/Q/−U`, C3's `S_struct/S_sem/cover/κ` are the same vector under different names; C1's
   `e(P)` (suppress tiny accidental motifs) and C3's `κ` (systematicity) even target the same
   failure mode from opposite ends.
4. **The same structural-encoding answer, converging on C2's own open question.** C2 flagged
   "how to encode directed typed graphs without losing edge direction/type" as its main uncertainty
   and proposed relation-type-specific directed matrices as one option; C1 independently built typed
   directed multiedge affinities into `K`; C3 independently implemented per-relation-type matrices
   plus transposes and measured that the hard negative separates. Three formulations, one answer:
   **structure must stay typed and directed per-relation; a single scalar structure matrix is the
   most likely way to adopt the right family and still fail.**
5. **The same rejections.** Exact GED / MCS / subgraph isomorphism as default (3/3 + H), learned
   graph matchers (3/3), semantic-Hungarian alone (C1, C2 explicitly; C3's α=0 measurement proves
   *why*: cross-domain correspondence accuracy 0.156), single blended scalar (3/3).
6. **The same granularity verdict.** Invariance F is Not Supported / Partial in all three and is
   handed to a separate multiscale layer (R0-D) rather than faked with edit costs. C1's "do not
   claim granularity invariance by assigning a low edit cost to arbitrary paths" and C3's hand-off
   agree exactly.
7. **The same Thought DNA.** Stable node ids, controlled roles (as gates/affinity), closed typed
   directed relation vocabulary, edge ids for parallel edges (C1) / multigraph semantics (C3),
   extraction confidence as weights, semantics as a soft optional term. No timestamps, no raw prose,
   no global ontology in the verifier.

# Material Disagreements

**D1. Which relaxation is primary: QAP-RRWM or FGW-CG?**
C1 argues RRWM expresses typed multiedge affinity natively and FGW handles typed multirelations
awkwardly; C2 argues pFGW handles partiality natively and FAQ is full-match biased; C3 shows a
multi-relational FGW that answers C1's typed-relations objection and measures α robust across
0.3–0.9, undercutting H's hyperparameter-trap objection. **Empirical.** All three fit the runtime
budget (C1: ~0.44 s/pair dense QAP measured; C3: 8.7 ms/pair CG measured; C2: sub-second target,
unmeasured) — numbers from different machines and implementations, so they establish *feasibility*,
not ranking. H's cost objection to FGW (O(n³) Sinkhorn tuning) is contradicted by both executed
runs, which used conditional-gradient, not entropic regularisation.

**D2. Unmatched-node mechanism: partial mass (C2), explicit unmatched costs in rounding (C1), or
ε-padding (C3).** Three mechanisms for one requirement; C1's calibrated `w_0` is the most
expressive, C3's padding the simplest, C2's mass grid the most principled. Representational, minor;
decide by what E-C1 (below) shows on fragments.

**D3. Non-convexity policy.** C1: multi-restart + local moves. C2: multi-start + parameter grid.
C3: measured the instability (generic-graph scores swing [0.00, 0.57] across relabelings) and
additionally measured that retrieval seeds buy determinism *at a small cost in correspondence
accuracy* (0.896 → 0.750 with sd → 0.000). Converged on "never trust one run"; C3's seed
measurement qualifies C1's "retrieval should hand seeds" and B-layer claims: **seeds are a latency/
stability tool, and at least one unseeded restart is mandatory.**

**D4. Reification of higher-order relations.** C1: convert hyperedges to relation nodes before
matching if needed. C3: unnecessary — the quadratic term couples relation pairs implicitly. H:
binary edges are a lossy stand-in for the higher-order `CAUSE[R1,R2]` that systematicity actually
scores. Partly terminological (C3's κ and H's systematicity reward the same connected structure),
partly real: none of the three tested a case where two graphs share all binary edges but differ in
higher-order binding. Cheap to add to the benchmark.

**D5. Score calibration.** C1 and C2 ship different hand-set weight vectors; C3 ships none and
flags cross-size normalisation as unsolved (fragment scores 0.393 against its own parent). C1's
evidence factor and C2's coverage term are candidate fixes. Open; belongs to R0-G.

# Assumption Matrix

| Assumption | C1 | C2 | C3 | Status |
|---|---|---|---|---|
| Hybrid beats any single algorithm | yes | yes | yes (measured vs α=0) | converged |
| Typed/directed structure must survive encoding | yes (K) | yes (option, flagged) | yes (measured) | converged |
| Candidate pruning won't delete the true cross-domain pair | assumed (top-d generous) | assumed | n/a (no pruning at toy scale) | untested (C1's own failure mode 2) |
| Generic motifs are the verifier's residual FP channel | via e(P) | via U penalty | measured: margin 0.23 | **confirmed by C3; needs idf weighting** |
| Verifier cost fits budget at 50×50, top-20 | measured ~9 s | targeted | measured 0.17 s | converged (feasible) |
| One ground-truth mapping exists per pair | denied (automorphism metrics) | partially | partially (labelling caveat) | converged: benchmark must be automorphism-tolerant |

# Experiments Needed

**E-C1 — the head-to-head.** C1's 200-pair toy benchmark spec (10 motifs × transformations × hard
negatives, automorphism-tolerant F1, ROC-AUC, runtime, memory) is the best-specified experiment in
either mission; run it with **all three primaries** — C1's QAP hybrid, C2's pFGW+rescore, C3's
multi-relational FGW (harness already exists in `research/experiments/`) — plus C1's semantic-
Hungarian baseline, on identical data and one machine. C1's own falsification thresholds
(F1 ≥ 0.80, hard-negative top-1 ≥ 0.90, ≤ 2 s/pair) adjudicate D1 directly.

**E-C2 — generic-motif margin under idf.** C3 measured the noisy-analog vs generic-chain margin at
0.23 unweighted; rerun with relation-pattern idf weighting (C3's own recommendation, C1's e(P),
C2's U as variants) and report whether the margin widens. Links directly to the B-review's E1.

**E-C3 — higher-order binding case (from D4).** Two pairs sharing all binary edges, differing only
in which relation governs which; decides reification cheaply.

**E-C4 — cross-size normalisation.** Fragment-vs-whole scoring across size ratios 1:2–1:8; adopt
whichever of {containment normalisation, C1's e(P)·coverage, C2's Q term} keeps a planted fragment's
score monotone in match quality rather than in size ratio.

# Consequences for Thought DNA

Identical to the union already listed by the three runs (stable ids, closed typed directed relations
with polarity, roles, per-edge ids for parallel relations, confidences, optional semantic feature) —
with one addition this review promotes from C1: **relation-type compatibility vectors** (a fixed
matrix saying `increases` is partially compatible with `causes` but not with `prevents`), because
every proposed affinity function silently needs one and no run defined it. This is a small, closed,
versioned artifact and should be specified in the Invariance Spec, not improvised per-implementation.

# Recommended Architecture Decision

Carry to the Verification ADR:

1. **Adopt the three-stage hybrid as the verifier pattern** (soft → consistency → discrete, partial
   injective output with components and unmatched nodes). 3/3 convergence including two blind runs;
   this is as settled as anything in R0.
2. **Mandate per-relation-type directed structural encoding** in whichever solver wins E-C1. The
   convergence on this point across three formulations — including the run that flagged it as its own
   open uncertainty — is the strongest purely-representational result in the C mission.
3. **Leave the primary-solver choice to E-C1**; both executed candidates fit budget, and the review
   declines to rank its sponsor's own entry ahead of a measured head-to-head.
4. **Seeds optional, one unseeded restart mandatory** (C3's measurement qualifying C1's interface
   request and B's hand-off claim).
5. **Granularity goes to R0-D's layer; verifier does not fake it.** 3/3.
6. Benchmark G inherits: automorphism-tolerant correspondence metrics (C1), same-vocabulary rewired
   and reversed negatives (all), the generic-motif margin case with idf variants (C3), the
   higher-order binding pair (D4), and fragment/whole size sweeps (E-C4).

# Confidence

**HIGH** on the pattern, output contract, and typed-directed encoding (items 1, 2, 5 — blind
convergence plus one executed confirmation). **MEDIUM** on primary-solver choice and score
calibration — genuinely open, cheap to close, and deliberately not prejudged given the reviewer's
conflict.

# Open Questions

1. E-C1's winner, and whether C1's dense-K memory wall (763 MiB unpruned at 100×100) or a sparse
   association-graph implementation decides it at the margins.
2. Whether the verifier's generic-motif margin under idf (E-C2) is wide enough that retrieval's
   precision problem (B review, E1) can be partially delegated downstream — the two experiments
   together settle how much precision each stage must supply.
3. Whether any real Thought corpus exhibits the automorphic/symmetric motifs C1 warns about at
   rates that make single-ground-truth benchmarks misleading.
4. The similarity oracle: all three runs stipulate node similarity; R0-E/R0-F own the real one, and
   every accuracy number in this mission inherits their error bars.
