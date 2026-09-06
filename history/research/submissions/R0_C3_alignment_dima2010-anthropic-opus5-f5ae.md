---
mission: R0-C
run: C3 (independent repeat)
contributor: dima2010
agent_or_model: Anthropic Claude Opus 5 (claude-opus-5), Claude Code CLI, high-effort mode
date: 2026-08-31
mission_modified: false
web_research_used: true
code_executed: true
blind_constraints_preserved: true
agent_id: dima2010-anthropic-opus5-f5ae
experiment: research/experiments/R0_C3_alignment_experiment.py
---

# Decision

**GO**, with one measured caveat that changes the design. The primary verifier should be
**multi-relational Fused Gromov-Wasserstein (FGW)** — Vayer et al.'s fused optimal-transport objective
extended so that structure is carried by *one adjacency matrix per relation type plus its transpose*,
rather than by a single scalar distance matrix — solved by conditional gradient, with unmatched nodes
handled by ε-node padding, followed by an SME-style structural-consistency filter and a Hungarian
extraction to a discrete injective mapping. The fallback is **spectral matching** (Leordeanu & Hebert)
over seeded candidate correspondences: ~20 lines of numpy, no dependency, graceful degradation.

I implemented this and ran it. On the master brief's own battery/organisation example the verifier
recovers **8/8 correct node correspondences across 12 random relabelings** for any α ≥ 0.3, and cleanly
rejects the project's hard negative. But the measured result also contains a warning that no amount of
tuning removed: **a generic 8-node causal chain scores `S_struct = 0.512` against a realistic noisy true
analogy's `0.740`.** A 0.23 margin is not a comfortable decision boundary. Structural agreement alone is
not sufficient; the verifier needs rarity weighting on relational patterns, not just structural fit.

# Confidence

**MEDIUM-HIGH** on the algorithm choice, **MEDIUM** on the operating point.

FGW's suitability is now backed by execution rather than argument, and its cost is measured, not
estimated. The uncertainty is the false-positive boundary: my test corpus is 9 hand-built graphs with a
*stipulated* semantic-similarity oracle, not a real corpus with a real encoder. The generic-chain margin
above is the thing most likely to get worse at scale, not better.

# Best Algorithm / Method

## The objective

Vayer et al. (2019) define the Fused Gromov-Wasserstein distance for a trade-off α ∈ [0,1] as

```
FGW_{q,α}(μ,ν) = min_{π ∈ Π(h,g)}  Σ_{i,j,k,l} [ (1−α)·d(a_i,b_j)^q  +  α·|C1_{i,k} − C2_{j,l}|^q ] · π_{i,j} · π_{k,l}
```

α = 0 recovers Wasserstein (features only); α = 1 recovers Gromov-Wasserstein (structure only). Despite
an apparent `O(m²n²)` tensor product, the sum simplifies to **`O(mn² + m²n)`** for q = 2 via the Peyré
et al. (2016) square-loss decomposition, and the problem is solved by conditional gradient (Frank-Wolfe):
each iteration takes a gradient, solves a linear OT subproblem, and line-searches.

**Why this is the right objective for Resonance.** α is literally the knob that trades vocabulary against
structure. The project's central hard negative — "same words, different structure" versus "different
words, same structure" — is a question about where you sit on α. No other candidate in the mission's list
exposes that trade-off as a single, tunable, interpretable parameter.

## The extension Resonance needs

Vanilla FGW collapses structure into **one scalar matrix** `C` per graph (usually shortest-path distance
or adjacency). Thought Graphs have *typed, directed, signed* edges, and that is where the cross-domain
meaning lives once entity vocabulary has been discarded. Collapsing `causes`, `prevents` and `precedes`
into one number destroys exactly the signal the verifier exists to read.

So define one structure matrix per relation type, **and include its transpose as a distinct type** so
edge direction enters the objective:

```
structure cost = Σ_{r ∈ R ∪ Rᵀ}  Σ_{i,j,k,l} | C1^{(r)}_{i,k} − C2^{(r)}_{j,l} |²  π_{i,j} π_{k,l}
```

Cost is `O(|R| · (mn² + m²n))` — with |R| ≈ 10 relation types and n = 50 this is still trivial, as the
measured runtimes below confirm. Direction-as-a-separate-type is what makes "stress causes insomnia" and
"insomnia causes stress" separable at all; without it they share an identical structure term.

## The hybrid: soft → consistent → discrete

Mission question 2 asks whether a hybrid beats one algorithm. **Yes**, and the measurements say why.

1. **Soft.** FGW returns a coupling matrix π — a soft correspondence that tolerates size differences and
   soft semantic similarity. This is the only stage that can absorb "these two concepts are 0.6 similar".
2. **Structural consistency.** π is not injective and not structurally validated. An SME-style pass
   enforces one-to-one mapping and parallel connectivity (if a relation is mapped, its arguments must be
   mapped consistently), and rewards *systematicity* — connected, deep matched structure over scattered
   local hits. I report this as κ, the largest connected component of the matched subgraph.
3. **Discrete.** Hungarian assignment on −π restricted to consistent hypotheses yields the final injective
   mapping the explanation layer needs.

Skipping stage 2 is the tempting shortcut and it is wrong: FGW is **non-convex**, and my measurements show
its structural score for generic graphs swinging across `[0.00, 0.57]` depending purely on node relabeling.
κ is what distinguishes "matched seven scattered edges" from "matched one coherent causal chain".

# Why It Fits Resonance

- **Deterministic, non-LLM, no training.** Conditional gradient on integer-typed adjacency matrices. The
  brief's hard constraints are met exactly.
- **Returns correspondences, not a scalar.** The mission's central requirement. π *is* the correspondence;
  the explanation layer gets "which branches correspond" for free.
- **Different sizes and partial matching** fall out of ε-node padding (below).
- **40–50h budget.** `POT` ships `ot.gromov.fused_gromov_wasserstein` and semi-relaxed variants. I did not
  even need it: the whole solver is ~60 lines of numpy, which is the real dependency-risk answer.

# Required Thought DNA

The verifier consumes strictly less than the retrieval stage does:

| Field | Level | Used for |
|---|---|---|
| `relation_type` (closed vocabulary) | edge | **the structure matrices — the primary signal** |
| `direction` | edge | separate transpose channel; the hard negative depends on it |
| `sign` (+/−) | edge | `prevents` must not collapse onto `causes` |
| `semantic_similarity(a,b)` | node pair | the feature cost `M`; may be an embedding cosine or a bucket match |
| `node_id` | node | correspondence bookkeeping and explanation |
| `extraction_confidence` | node/edge | optional cost down-weighting |

**Not required:** global graph embeddings, ontology URIs, timestamps, higher-order reification, node
role classes. The verifier needs a *similarity function* between nodes, not their internal features — which
means the ontology question (R0-E) can be answered independently of this decision.

# Required Graph Representation

**Directed labelled multigraph.** Multigraph because one node pair can carry two relations
(`A causes B` and `A precedes B`) and the per-type decomposition handles them as independent channels at
no extra conceptual cost. Directed because direction is a separate structure channel.

**Reification is not required.** Higher-order structure is captured implicitly: a matched two-step path
`A→B→C` already constrains three nodes jointly through the quadratic term. SME needs explicit higher-order
predicates because it matches predicate trees; FGW does not, because the quadratic objective already
couples node pairs. This is a real simplification of Thought DNA and it is worth taking.

# Invariances

Measured where marked ✔; reasoned otherwise.

| Transformation | Supported | Partially | Not | Mechanism / evidence |
|---|---|---|---|---|
| A paraphrase | ✅ ✔ | | | `S_struct = 1.000`, correspondence 1.000 at all α |
| B vocabulary substitution | ✅ ✔ | | | same run; synonym similarity 0.85 suffices |
| C node ordering | ✅ ✔ | | | 12 random relabelings, identical scores |
| D irrelevant branch insertion | | ⚠️ ✔ | | NOISY case (branch + deletion + mislabel): `S_struct` 1.000 → 0.740 |
| E partial observation | | ⚠️ ✔ | | 4-node fragment vs 8-node: `S_struct = 0.393`, κ = 0.88 — found, but score not size-comparable |
| F different granularity | | ⚠️ | | inserted intermediate node degrades the path; hand to R0-D |
| G different graph sizes | | ⚠️ ✔ | | ε-node padding works; absolute scores are **not** comparable across size pairs |
| H domain substitution | ✅ ✔ | | | `S_struct = 1.000`, 8/8 correspondences, `S_sem = 0.05` — the headline result |
| I extraction mistakes | | ⚠️ ✔ | | one mislabeled relation costs ~0.09 of `S_struct` |

The honest weak entry is **E/G together**: a fragment scores 0.393 not because the match is bad but
because `S_struct` normalises by `max(|E1|,|E2|)`. Cross-size score comparability is unsolved here and
must be fixed before any global threshold is set.

# Retrieval vs Verification

**EXPENSIVE VERIFICATION**, unambiguously.

- **Input:** two Thought Graphs, a node-similarity function, and optionally seed correspondences.
- **Output:** injective node mapping φ, the matched relational subgraph, and the score vector below.

## The seeding question — a partial correction to R0-B2

**Disclosure: I authored R0-B2**, the retrieval-side run, which claimed retrieval should hand the verifier
seed node correspondences. This run is therefore *not* independent of B2, and I treated that claim as a
hypothesis to test rather than a premise. FGW is non-convex, so seeding is directly measurable.

Seeding the initial coupling with 0–3 true correspondences, α = 0.7, noisy cross-domain case, 12
relabelings:

| seeds | correspondence accuracy | `S_struct` |
|---|---|---|
| 0 | **0.896** (sd 0.112) | 0.667 (sd 0.059) |
| 1 | 0.885 (sd 0.095) | 0.656 (sd 0.054) |
| 2 | 0.771 (sd 0.069) | 0.740 (sd 0.035) |
| 3 | 0.750 (sd **0.000**) | **0.750** (sd 0.000) |

**Seeds buy determinism and structural fit; they do not buy correctness.** Accuracy *falls* from 0.896 to
0.750 as seeds are added, while variance collapses to zero and structural agreement rises. Seeds pin
Frank-Wolfe into one basin — a basin with better structural agreement than the ground truth I stipulated.
(Part of that gap is arguably my labelling: in the noisy case an inserted node makes two mappings
structurally defensible.) B2's claim should therefore be **qualified, not repeated**: seeds are a
determinism and latency optimisation, not an accuracy one, and a verifier that must maximise
correspondence accuracy should run at least one unseeded restart.

# Computational Cost

Measured on this machine, single core, pure numpy, ~60-line CG solver, α = 0.7, average degree 2.5:

| graph pair | per pair | top-20 candidates |
|---|---|---|
| 10 × 10 | 3.3 ms | 0.07 s |
| 25 × 25 | 4.6 ms | 0.09 s |
| **50 × 50** | **8.7 ms** | **0.17 s** |
| 100 × 100 | 23.6 ms | 0.47 s |

Growth is far below the `O(|R|(mn²+m²n))` worst case because iteration count, not per-iteration cost,
dominates at these sizes. **Verification is not the bottleneck.** A full top-20 verification costs less
than a fifth of a second, which means the architecture can afford a larger K than the brief assumes, or a
second unseeded restart per candidate, essentially for free.

# Existing Implementations

| Library | Use | Maturity / risk |
|---|---|---|
| **POT** (`ot.gromov.fused_gromov_wasserstein`) | reference FGW, semi-relaxed FGW, quantized FGW, barycenters | JMLR-published, actively maintained, multiple backends. **Note:** POT documents that its Bregman-projection solver may return a coupling violating marginals and a possibly negative loss — read the solver variant before trusting the number |
| **numpy + scipy only** | the ~60-line CG solver used here | zero dependency risk; recommended for MVP |
| **scipy** `linear_sum_assignment` | LP oracle and discrete extraction | mature, rectangular support |
| **srGW** (Vincent-Cuaz et al.) | semi-relaxed GW, relaxes one marginal | research code; the principled alternative to ε-padding |
| **networkx** | graph handling, connectivity for κ | mature |
| SME implementations (QRG) | structural-consistency reference | research code, Lisp lineage; reimplement the consistency rules rather than adopt |

Reject for MVP: exact **GED**, **maximum common subgraph**, and **subgraph isomorphism**. All are NP-hard,
none tolerate soft labels natively, and none give a graded cross-domain score.

# Minimal Pseudocode

```python
# structure: one matrix per relation type PLUS its transpose (direction)
TYPES = RELS + [r + "^T" for r in RELS]

def tensor(C1, C2, pi):                      # Peyre et al. 2016, square loss
    p, q = pi.sum(1), pi.sum(0)              # f1(a)=a^2, f2(b)=b^2, h1(a)=a, h2(b)=2b
    return (C1**2) @ p[:,None] @ ones(1,m) + ones(n,1) @ q[None,:] @ (C2**2).T \
           - 2 * C1 @ pi @ C2.T

def fgw(g1, g2, alpha, iters=200):
    N  = max(g1.n, g2.n)
    g1, g2 = pad(g1, N), pad(g2, N)          # eps-nodes: a match to one IS "unmatched"
    M  = 1 - semantic_similarity(g1, g2)
    pi = ones((N,N)) / (N*N)
    for _ in range(iters):
        grad = (1-alpha)*M + alpha*2*sum(tensor(g1.C[t], g2.C[t], pi) for t in TYPES)
        ri, ci = linear_sum_assignment(grad)             # LP oracle
        direction = zeros((N,N)); direction[ri,ci] = 1/N
        pi = line_search(pi, direction, energy)          # Frank-Wolfe step
    return pi

def verify(g1, g2, pi):
    phi = hungarian(-pi)                                 # discrete injective map
    phi = structural_consistency_filter(phi, g1, g2)     # SME-style parallel connectivity
    return score(g1, g2, phi)
```

## Scoring equation (mission question 6)

Report a **vector, never a blend** — the hard negative is only decidable if the components stay separate:

```
S_struct(φ) = Σ_{(u,v,r) ∈ E1 : (φu,φv,r) ∈ E2} idf(r)      /  Σ_{(u,v,r) ∈ E1} idf(r)
S_sem(φ)    = mean_{u ∈ dom φ} sim(u, φu)
cover(φ)    = |dom φ| / min(|V1|, |V2|)
κ(φ)        = largest connected component of the matched subgraph / |dom φ|

resonance(φ) = κ(φ) · S_struct(φ) · cover(φ)        reported ALONGSIDE S_sem, not multiplied by it
```

Classification follows directly from the pair `(S_struct, S_sem)`:

| S_struct | S_sem | verdict |
|---|---|---|
| high | low | **cross-domain analogy — the valuable case** |
| high | high | same-domain near-duplicate |
| low | high | *same words, different structure* → reject |
| low | low | unrelated |

The `idf(r)` weighting in `S_struct` is **not** decoration — see Failure Modes.

# Toy Experiment

Already executed. `research/experiments/R0_C3_alignment_experiment.py`, pure numpy/scipy, runs in seconds.
Nine graphs: the brief's battery chain as base; a paraphrase; the organisation cross-domain analogue; a
noisy analogue (inserted branch + deleted edge + mislabeled relation); a 4-node fragment; and three
negatives — "same words, rewired into a star", a short generic chain, a long generic chain. Every case is
scored over **12 random node relabelings**, because in a first version I built the graphs in matching node
order and every score was an artifact of construction order; permutation is what makes the numbers mean
anything.

Headline results (mean over 12 relabelings):

| case | α = 0 | α = 0.7 |
|---|---|---|
| paraphrase | `S_struct` 1.000 | 1.000 |
| **cross-domain analogy** | **0.083**, corr. 0.156 | **1.000**, corr. **1.000** |
| noisy cross-domain | 0.052 | 0.740 |
| 4-node fragment | 0.179 | 0.393 |
| *same words, rewired* (neg) | 0.143, `S_sem` **1.000** | 0.143, `S_sem` **1.000** |
| generic long chain (neg) | 0.107 | **0.512** |

**Pure semantics cannot do cross-domain analogy at all** (`S_struct` 0.083, correspondence 0.156) and any
α ≥ 0.3 solves it perfectly on the clean case. That threshold is the empirical answer to mission
question 5.

**My own falsification check was too lenient, and I am reporting that rather than hiding it.** I wrote
check F3 as "clean cross-domain minus generic ≥ 0.3", which passes comfortably (1.000 − 0.512). The
honest comparison is the *realistic* positive against the same negative: **0.740 vs 0.512, a margin of
0.23.** A reviewer should treat that, not F3, as the real result.

# Failure Modes

1. **Generic-chain collapse (the measured one).** A structurally trivial 8-node causal chain reaches
   `S_struct = 0.512` against a real noisy analogy's 0.740. Any corpus is full of `X causes Y causes Z`.
   **Mitigation: `idf(r)` weighting** — rare relational patterns must count more than common ones, exactly
   as in text retrieval. Unweighted structural agreement is not a usable decision statistic.
2. **Non-convexity.** Frank-Wolfe converges to different local optima under pure relabeling: generic-chain
   `S_struct` ranges `[0.00, 0.57]` across 12 runs of the *same* pair. Any single-restart score is a
   sample, not a measurement. Multi-restart or seeding is mandatory; see the seeding table for the
   accuracy/determinism trade.
3. **Cross-size incomparability.** A 4-node fragment scores 0.393 against its own 8-node parent purely
   from `max(|E1|,|E2|)` normalisation. A global threshold applied across size pairs will silently prefer
   equal-size matches.
4. **Isometry invariance.** GW-family objectives match structure, and structure has symmetries. A graph and
   a relabeled automorphic variant are indistinguishable to the structure term; only the feature term
   breaks the tie, which is precisely the term cross-domain matching turns down.
5. **Stipulated similarity oracle.** My `sim()` is hand-written (1.0 / 0.85 / 0.05). A real encoder gives a
   smeared distribution in which α's safe range will be narrower than measured here. This is the single
   largest gap between this experiment and reality.
6. **Sign/direction erasure.** If `prevents` is folded into `causes`, or transposes are dropped, the
   rewired hard negative stops being detectable — its `S_struct` rises toward the true analogy's.
7. **Balanced-transport artifacts.** Without ε-padding, standard FGW forces all mass to move, so irrelevant
   branches get confidently matched to something. Padding (or semi-relaxed FGW) is not optional.

# What NOT To Build

- **Exact GED / MCS / subgraph isomorphism.** NP-hard, no soft labels, no graded cross-domain score.
- **A single blended score.** Multiplying `S_struct` by `S_sem` makes the project's hard negative
  undecidable — a mid score would be unattributable.
- **A learned graph-matching network.** Violates the no-new-model constraint and forfeits the
  explainability that π gives for free.
- **Vanilla single-matrix FGW.** Collapsing typed, directed edges into one scalar distance matrix discards
  the exact signal cross-domain analogy depends on. This is the most likely way to adopt the right paper
  and still fail.
- **Full SME reimplementation.** Weeks of work; its consistency rules are worth borrowing, its
  predicate-calculus machinery is not.
- **Trusting a single FGW run.** See failure mode 2.

# Architecture Consequences

1. Verification is **cheap** — 8.7 ms per 50×50 pair, 0.17 s for top-20. Budget K generously.
2. The verifier needs **typed, directed, signed** edges and a node-similarity function; nothing else.
3. Structure must be **one matrix per relation type plus transpose**, never one scalar matrix.
4. `α` is a first-class tunable with an empirical safe range of roughly **0.3–0.9**; expose it, do not
   hard-code it.
5. `S_struct` must be **idf-weighted over relational patterns** or generic chains will dominate results.
6. Scores are **vectors**; the API must never collapse them.
7. Cross-size score normalisation is **unsolved** and blocks any global threshold.
8. Seeds from retrieval buy **determinism, not accuracy** — plan at least one unseeded restart.
9. **Reification is unnecessary** for verification; the quadratic term captures higher-order structure.
10. Verification results are only as good as the similarity oracle, which makes R0-E/R0-F upstream
    dependencies of this decision's real-world accuracy.

# Mission Questions — Direct Answers

1. **Primary:** multi-relational FGW (α ≈ 0.5–0.7) + SME-style consistency + Hungarian extraction.
   **Fallback:** spectral matching (Leordeanu & Hebert) over seeded candidate pairs.
2. **Hybrid, yes** — measured. The soft stage absorbs semantic softness and size differences; the
   consistency stage supplies κ, which is what separates coherent from scattered matches under a
   non-convex objective.
3. **Input features:** per-type adjacency (with transposes), edge sign, node-pair similarity matrix,
   optional confidences and seeds.
4. **Unmatched nodes:** ε-node padding — implemented and verified; a match to an ε-node *is* non-matching.
   Semi-relaxed FGW is the principled alternative.
5. **Cross-domain without semantic collapse: yes, and the threshold is measured.** At α = 0 the
   cross-domain case scores 0.083; at α ≥ 0.3 it scores 1.000 with perfect correspondence. What prevents
   collapse is that the *typed relation vocabulary* carries the meaning once entity vocabulary is
   discounted — so the closed relation vocabulary is a hard requirement for verification too.
6. **Scoring equation:** see above — an idf-weighted vector, deliberately unblended.
7. **Runtime:** 8.7 ms per 50×50 pair; 0.17 s for top-20. Measured, not estimated.
8. **Thought DNA:** typed + directed + signed edges and a node-similarity function; no reification, no
   ontology, no role classes needed by *this* stage.

# Sources

1. **Vayer, T., Chapel, L., Flamary, R., Tavenard, R., & Courty, N. (2019). "Optimal Transport for
   structured data with application on graphs." ICML 2019.** The primary source. The FGW objective, the
   α trade-off, the conditional-gradient solver and the `O(mn²+m²n)` simplification quoted above are taken
   from the paper's own text. https://arxiv.org/abs/1805.09114
2. **Peyré, G., Cuturi, M., & Solomon, J. (2016). "Gromov-Wasserstein Averaging of Kernel and Distance
   Matrices." ICML 2016.** The square-loss tensor decomposition that makes the quadratic term tractable —
   the reason this runs in milliseconds rather than seconds.
3. **Vincent-Cuaz, C., Flamary, R., Corneli, M., Vayer, T., & Courty, N. (2022). "Semi-relaxed
   Gromov-Wasserstein divergence with applications on graphs." ICLR 2022.** Relaxes one marginal, the
   principled alternative to ε-padding for partial matching. https://arxiv.org/abs/2110.02753
4. **Bai, Y. et al. (2025). "Fused Partial Gromov-Wasserstein for Structured Objects."** Extends FGW to
   unbalanced data with Frank-Wolfe and Sinkhorn solvers; relevant if fragment/whole comparability becomes
   blocking. https://arxiv.org/abs/2502.09934
5. **Falkenhainer, B., Forbus, K., & Gentner, D. (1989). "The Structure-Mapping Engine: Algorithm and
   Examples." Artificial Intelligence 41(1).** Source of the structural-consistency and systematicity
   constraints borrowed for stage 2, and of the principle that relational matches outrank attribute
   matches. https://groups.psych.northwestern.edu/gentner/papers/FalkenhainerForbusGentner89.pdf
6. **Gentner, D. (1983). "Structure-Mapping: A Theoretical Framework for Analogy." Cognitive Science 7(2).**
   Why systematicity (κ here) is the right thing to reward.
7. **Leordeanu, M., & Hebert, M. (2005). "A Spectral Technique for Correspondence Problems Using Pairwise
   Constraints." ICCV 2005.** The recommended fallback: build an affinity matrix over candidate
   correspondences, take its principal eigenvector, extract a consistent assignment greedily.
8. **Gold, S., & Rangarajan, A. (1996). "A Graduated Assignment Algorithm for Graph Matching." IEEE TPAMI
   18(4).** The QAP-relaxation lineage this solver sits in; softassign/deterministic annealing is the
   drop-in replacement if Frank-Wolfe's local minima prove troublesome.
9. **Flamary, R. et al. (2021). "POT: Python Optimal Transport." JMLR 22.** The reference implementation
   (`ot.gromov`), including the semi-relaxed and quantized variants, and the documented caveat that some
   solvers may violate marginals. https://pythonot.github.io/
10. **Bunke, H., & Allermann, G. (1983); and the QAP formulation of GED (arXiv:1512.07494).** Establishes
    the ε-node convention used here for unmatched nodes, and why exact GED is not viable at this scale.

---

## Provenance and independence

- **Run type:** independent repeat `R0-C3` under `REPEAT_CLAIM` on issue #6. Non-exclusive; it neither
  claims nor blocks canonical R0-C1 (PR #30) or R0-C2 (merged).
- **Why this repeat exists:** R0-C1 recommended Claude Opus 5 but ran on GPT-5 Codex, and R0-C2 ran on
  GPT-5.6 Sol. Both halves of a blind pair whose purpose is independent convergence came from one model
  family. This run supplies the Anthropic-family third point.
- **Blind constraint (R0-C):** preserved and enforced **mechanically**, not by discipline. R0-C2 is merged
  into `main`, so it was removed from this run's working tree with `git update-index --skip-worktree`
  before any mission work began; `cat` on that path fails. R0-C1 (PR #30) is unmerged and was never
  present. Only `CLAIM`/`SUBMIT` coordination headers were read, per `work/STATE_MACHINE.md`.
- **Disclosed dependency:** I authored R0-B2, so this run is **not** independent of it. B2's seed-handoff
  claim was tested rather than assumed, and the measurement **partially contradicts it** — reported in
  full above rather than smoothed over. R0-A, R0-D, R0-H and R0-F submissions were left unread.
- **Code executed:** yes — `research/experiments/R0_C3_alignment_experiment.py`, numpy 2.0.2 / scipy 1.13.1
  / Python 3.9.6, no network. All tables above are its output. Deterministic given the printed seeds.
- **Known limitations, stated plainly:** the semantic-similarity oracle is stipulated by hand, not produced
  by an encoder; graphs are 4–9 nodes, not 50; there is no real corpus, so no false-positive rate at scale;
  and the generic-chain margin (0.23) is measured on a single adversarial pair, not a distribution.
- **A first version of this experiment was wrong** and its results discarded: the target graphs were built
  in the same node order as the base, so identity was trivially recoverable and every score was inflated.
  Random relabeling fixed it. The `numpy` divide-by-zero warnings visible on this platform were separately
  verified as spurious BLAS flags — reproducible on trivial all-finite input with correct finite output.
