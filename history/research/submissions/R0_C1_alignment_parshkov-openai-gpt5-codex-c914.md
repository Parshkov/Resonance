---
mission: R0-C
run: C1
contributor: Parshkov
agent_id: parshkov-openai-gpt5-codex-c914
agent_or_model: GPT-5-based Codex (exact deployed model/version not exposed to this run)
date: 2026-08-31
mission_modified: false
web_research_used: true
blind_constraints_preserved: true
code_execution_used: true
additional_agents_used: false
notes: C2's submission, pull request, and result content were not inspected before this report was finalized.
---

# Decision

**Qualified GO:** use a sparse, typed Lawler quadratic-assignment (QAP) verifier, solved as a hybrid `candidate pairs -> RRWM soft structural consistency -> partial Hungarian rounding -> exact discrete rescoring/local improvement`. Its variables are candidate node correspondences; unary terms score compatible node roles and optional semantics, while pairwise terms score preservation of directed, typed relations. Keep partial Fused Gromov-Wasserstein (pFGW) as the fallback proposal generator for unusually noisy or weakly anchored pairs, not as the final judge. The final output must be a partial injective mapping plus component scores and unmatched nodes, never the relaxation's scalar objective alone.

# Confidence

**MEDIUM.** QAP directly expresses the required correspondence and relation constraints, and maintained Python implementations exist. The main uncertainty is empirical: there is no labeled Thought Graph corpus, so candidate pruning, relation compatibility, unmatched penalties, and score calibration are unvalidated. RRWM is non-convex and its readily available implementation uses a dense affinity matrix. This is a GO for a falsifiable verifier prototype, not for freezing the production matcher.

# Best Algorithm / Method

For graphs `G_A=(V_A,E_A)` and `G_B=(V_B,E_B)`, create a candidate set `C={(i,j)}` after hard incompatibility gates (for example, evidence cannot map to goal) and a generous top-`d` role/semantic shortlist. Let binary `x_ij` mean that node `i` maps to node `j`, with row and column sums at most one.

Use a non-negative Lawler affinity matrix `K`:

- diagonal `K[(i,j),(i,j)] = w_n u(i,j)`, where `u` combines node-type compatibility, functional-role similarity, semantic similarity, and extraction confidence;
- off-diagonal `K[(i,j),(k,l)] = w_e v(i->k,j->l)`, where `v` is the best confidence-weighted compatibility between the directed multiedges on those endpoints. Reversed direction receives zero unless the relation ontology explicitly declares symmetry.

RRWM computes a soft vector `z` by random walks on this association graph with reweighted jumps enforcing one-to-one constraints. Round `log(z_ij+epsilon)+lambda*u(i,j)` with a Hungarian assignment that has explicit unmatched scores. Then use add/drop/swap local moves against the signed discrete objective

`J(P) = w_n sum_(i,j in P) u(i,j) + w_e C(P) - w_x D(P) - w_0 (|V_A|+|V_B|-2|P|)`,

where `C(P)` is confidence-weighted compatible directed-edge mass, `D(P)` is induced edge mass whose direction/type is not preserved, and `w_0` is the calibrated unmatched cost. This last pass matters because RRWM requires non-negative affinities and therefore should propose, not adjudicate, mismatches.

Return both `J` and an interpretable `[0,1]` score:

`N = mean node compatibility; R = 2*C/(W_A+W_B); Q = 2*|P|/(|V_A|+|V_B|); resonance = e(P)*(0.25*N + 0.55*R + 0.20*Q)`,

where `W_A,W_B` are the total confidence-weighted induced relation masses and `e(P)=min(1,|P|/5)*min(1,C/4)` suppresses accidental one-edge motifs. These initial weights are benchmark parameters, not truths.

**Fallback:** run unregularized pFGW over several transported-mass fractions (for example 0.3, 0.5, 0.7, 0.9), using node cost `M` and asymmetric structural cost matrices, then feed its highest-mass pairs into the same partial rounding and exact scorer. pFGW tolerates unmatched mass, but its fractional many-to-many coupling, non-convexity, mass hyperparameter, and awkward handling of multiple directed relation types make it unsuitable as the sole verifier.

# Why It Fits Resonance

The QAP variables are the explanation Resonance needs: each selected variable is a node correspondence, and every pairwise contribution identifies preserved or contradicted relations. Soft node affinity admits paraphrase and uncertain extraction; the quadratic term prevents identical vocabulary from winning when relations disagree. Typed relation affinity permits cross-domain matching without requiring domain nouns to be close, provided the extractor supplies comparable functional roles and relation types. Partial rounding and explicit unmatched costs handle unequal graphs and irrelevant branches. Top-K verification allows this NP-hard objective to be approximated with several starts and local improvement rather than weakened into a retrieval metric.

# Required Thought DNA

Each node must contain exactly:

- a stable node identifier, so the verifier can emit a mapping;
- a controlled functional type/role used by compatibility gates and `u`;
- a normalized semantic feature or concept representation used as a soft, optional term in `u`;
- extraction confidence/salience used to weight unary evidence and unmatched cost.

Each relation must contain exactly:

- source and target node identifiers (direction is significant);
- a controlled relation type, or a fixed compatibility vector over relation types;
- extraction confidence used in `C`, `D`, and `v`;
- a relation identifier when parallel edges share endpoints, so multiedge correspondences can be explained.

No provenance text, timestamps, author identity, or raw prose is consumed by this verifier.

# Required Graph Representation

A **directed, typed property multigraph**. Direction and edge type are first-class because causal reversal and relation substitution are hard negatives; parallel claims must not be collapsed. Convert a hyperedge to a relation/event node with typed argument edges before matching. The solver receives sparse endpoint lists plus node/edge feature arrays; it does not require a tree or a single scalar adjacency matrix.

# Invariances

| Transformation | Supported | Partially | Not Supported | Mechanism |
|---|:---:|:---:|:---:|---|
| A. paraphrase | | X | | normalized semantic features and unchanged roles/relations |
| B. vocabulary substitution | | X | | role gates and structural affinity can outweigh lexical distance |
| C. node ordering | X | | | QAP is permutation invariant |
| D. irrelevant branches | | X | | unmatched assignments and induced-subgraph scoring; outliers can still distort RRWM |
| E. partial observation/missing nodes | | X | | partial mapping and unmatched cost |
| F. different granularity | | | X | one-to-one nodes/direct edges do not equate `A->B` with `A->X->Y->B` |
| G. different graph sizes | X | | | rectangular assignment with unmatched nodes |
| H. domain substitution, structure preserved | | X | | functional roles and relation types drive `v`; schema alignment is still required |
| I. modest extraction mistakes | | X | | confidence weighting, soft affinity, and unmatched nodes |

# Retrieval vs Verification

**EXPENSIVE VERIFICATION only.** Input is a retrieved pair of Thought Graphs plus optional retrieval seeds. Output is the discrete node mapping, mapped multiedges, unmatched nodes/edges, node/structure/coverage/evidence scores, total score, and the top contradictions. It creates no 1M-thought index. Retrieval should hand it seeds or candidate node pairs when available, not merely a candidate thought ID.

# Computational Cost

With `p=|C|` candidate node pairs and `I` RRWM iterations, a dense implementation costs `O(p^2)` memory and approximately `O(I*p^2)` time; Hungarian rounding is `O(max(n_A,n_B)^3)`. Exact rescoring is linear in induced edges per mapping, while a bounded local search multiplies that by the number of accepted/tested moves. The underlying QAP remains NP-hard, so multiple starts improve robustness but do not prove optimality.

For 50 vs 50 without pruning, `p=2,500` and `K` has 6.25M entries: about 25 MiB in float32 or 47.7 MiB in float64. A local synthetic run with seed 914, 12-dimensional node features, five one-hot relation types, and 125 directed typed edges per graph measured 0.268 s to build `K`, 0.173 s for 50 RRWM iterations, and under 1 ms for Hungarian rounding (Apple M1 Pro, one BLAS thread, Python 3.12.8, NumPy 2.5.2, pygmtools 0.6.0). The second graph retained 85% of permuted edges, filled the rest with random edges, and added Gaussian node-feature noise with standard deviation 0.03. It recovered the planted permutation in that easy case; this is a runtime smoke test, not accuracy evidence.

Twenty full 50x50 candidates therefore take roughly 9 seconds sequentially on that machine before feature extraction and local rescoring; peak memory is per candidate if processed sequentially. Capping each node at 10 candidates gives `p<=500`, but pygmtools' current builder still materializes the full `n_A*n_B` layout; exploiting that reduction requires a sparse/custom association-graph implementation. At 100x100, an unpruned float64 `K` is about 763 MiB, so dense unpruned verification is a NO-GO.

The pFGW fallback has the usual factored squared-loss cost around `O(n_A^2*n_B+n_A*n_B^2)` per conditional-gradient iteration, but multiply this by mass settings and restarts. A 50x50 POT smoke call completed in milliseconds; convergence and accuracy, not that toy runtime, are the risk.

# Existing Implementations

- **pygmtools 0.6.0:** NumPy backend, affinity construction, RRWM, IPFP, A*, and Hungarian. It installed as a Python 3.12 wheel and reproduced a 50-node smoke test. Risks: dense `p^2` affinity storage, computer-vision-oriented examples, and unmatched scores are exposed in Hungarian but not directly in RRWM.
- **SciPy `linear_sum_assignment`:** mature rectangular Jonker-Volgenant rounding; pad explicit dummy rows/columns to express per-node unmatched costs. It does not solve the quadratic stage.
- **POT 0.9.7.post1:** maintained unregularized/entropic partial FGW and fused unbalanced GW solvers. Risks: non-convex initialization, transported-mass/regularization tuning, fractional output, and one structural matrix rather than native typed multirelations.
- **NetworkX GED/VF2:** useful only as an oracle on tiny cases. GED exposes a timeout and current-best answer; exact edit distance, MCS, and subgraph isomorphism are not credible 50-node default verifiers.

# Minimal Pseudocode

```text
verify(A, B, seeds=None):
    C = compatible_pairs(A.nodes, B.nodes, top_d=10, keep=seeds)
    K = zeros(|C|, |C|)
    for a=(i,j) in C:
        K[a,a] = wn * max(node_affinity(i,j), 0)
    for a=(i,j), b=(k,l) in nonconflicting(C):
        K[a,b] = we * directed_multiedge_affinity(i,k,j,l)

    soft = best_of_restarts(RRWM(K))
    P = hungarian(log(soft+eps) + lambda*node_affinity,
                  unmatched_scores(A), unmatched_scores(B))
    P = local_add_drop_swap(P, objective=J, max_moves=500)

    if unstable(P) or too_few_candidates(P):
        T = best_partial_FGW(A, B, masses=[.3,.5,.7,.9])
        P = round_and_locally_score(T, objective=J)

    return mapping(P), matched_edges(P), unmatched(P), score_components(P)
```

# Toy Experiment

In under two hours, generate 200 pairs from ten hand-authored 12-node directed, typed causal motifs. Plant a mapping, permute nodes, replace all domain nouns, then independently add 30% irrelevant nodes/edges and delete 20% of observed nodes. For each positive, create hard negatives with the same node labels/features but (a) rewired causal edges, (b) reversed causal direction, and (c) incompatible relation types. Add a granularity-split variant as an expected failure/control.

Compare QAP hybrid, semantic-only Hungarian, pFGW+rounding, and NetworkX GED with a 2-second timeout. Measure planted correspondence precision/recall/F1, positive-vs-hard-negative ROC-AUC, top-1 choice of positive over its hard negatives, runtime, and peak memory. Falsify this recommendation if the hybrid has correspondence F1 below 0.80, hard-negative top-1 below 0.90, ROC-AUC below 0.90, fails to beat semantic Hungarian by 0.15 F1 on vocabulary substitution, or exceeds 2 seconds per 50x50 pair after candidate pruning. Report granularity failure rather than tuning it away.

# Failure Modes

1. Symmetric/automorphic motifs admit several equally valid mappings; a single “ground truth” is misleading.
2. Candidate pruning on semantic similarity removes the true cross-domain pair before structure can rescue it.
3. A generic hub-to-hub match dominates many edge rewards despite wrong causal meaning.
4. Relation ontology drift makes identical structures appear incompatible, or overly broad relation types create false positives.
5. One concept split into several nodes violates the injective mapping and defeats granularity invariance.
6. Tiny common motifs score perfectly by chance; the evidence factor is necessary but must be calibrated.
7. Dense 100-node graphs exhaust memory through `p^2` affinities.
8. Extraction makes correlated errors in both graphs, producing confident but spurious structural agreement.
9. RRWM/local search converges to different local optima across initializations.
10. An incorrect symmetric-edge encoding hides causal reversal.

# What NOT To Build

- Do not use exact GED, maximum common subgraph, VF2, or A* as the 50-node default; reserve them for tiny test oracles.
- Do not use pure FGW/pFGW as the final score: fractional coupling and collapsed relation structure weaken the required explanation.
- Do not use semantic Hungarian alone; it cannot distinguish same words with different structure.
- Do not allocate an unpruned dense QAP affinity at 100x100.
- Do not train a neural graph matcher for R0; it adds data requirements and model dependence without a corpus.
- Do not claim granularity invariance by assigning a low edit cost to arbitrary paths; require a separate multiscale representation and benchmark.

# Architecture Consequences

- Preserve directed typed relations and parallel edges in Thought DNA.
- Preserve normalized functional node roles independently of domain vocabulary.
- Store extraction confidence on nodes and edges.
- Retrieval should return optional seed correspondences.
- Make “unmatched” an explicit outcome with calibrated costs.
- Emit component scores and contradictions, not one opaque scalar.
- Implement candidate-pair gates before constructing QAP affinities.
- Process top-K sequentially or with a memory-aware concurrency cap.
- Add automorphism-tolerant correspondence metrics to the benchmark.
- Treat granularity as a separate architecture layer, not a verifier hyperparameter.

# Sources

1. [Lawler, “The Quadratic Assignment Problem” (1963)](https://doi.org/10.1287/mnsc.9.4.586) — defines the general quadratic form that can hold unary and pairwise correspondence affinity.
2. [Cho, Lee & Lee, “Reweighted Random Walks for Graph Matching” (ECCV 2010)](https://doi.org/10.1007/978-3-642-15555-0_36) — primary RRWM algorithm; association-graph random walks and robustness motivation.
3. [Leordeanu, Hebert & Sukthankar, “An Integer Projected Fixed Point Method for Graph Matching and MAP Inference” (NeurIPS 2009)](https://proceedings.neurips.cc/paper/2009/hash/fc2c7c47b918d0c2d792a719dfb602ef-Abstract.html) — practical discrete QAP refinement/fallback solver and explicit unary/pairwise formulation.
4. [pygmtools RRWM documentation](https://pygmtools.readthedocs.io/en/latest/api/_autosummary/pygmtools.classic_solvers.rrwm.html) — maintained Python API, iteration model, dimensions, and warm starts.
5. [pygmtools Hungarian documentation](https://pygmtools.readthedocs.io/en/latest/api/_autosummary/pygmtools.linear_solvers.hungarian.html) — partial rounding with per-node unmatched scores and cubic cost.
6. [Vayer et al., “Optimal Transport for structured data with application on graphs” (ICML 2019)](https://proceedings.mlr.press/v97/titouan19a.html) — introduces FGW's joint feature/structure objective and explains its graph use.
7. [Chapel, Alaya & Gasso, “Partial Optimal Transport with Applications on Positive-Unlabeled Learning” (NeurIPS 2020)](https://proceedings.neurips.cc/paper/2020/hash/1e6e25d952a0d639b676ee20d0519ee2-Abstract.html) — partial Wasserstein/GW constraints and conditional-gradient solver.
8. [POT `partial_fused_gromov_wasserstein` documentation](https://pythonot.github.io/master/gen_modules/ot.gromov.html#ot.gromov.partial_fused_gromov_wasserstein) — immediately usable pFGW implementation and its transport-plan output.
9. [Blumenthal & Gamper, “On the exact computation of the graph edit distance” (2020)](https://doi.org/10.1016/j.patrec.2018.05.002) — establishes exact GED's NP-hardness and severe search cost.
10. [SciPy `linear_sum_assignment` documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html) — mature rectangular assignment implementation for deterministic rounding.

**Conclusion: QUALIFIED GO** for the typed sparse-QAP hybrid, contingent on the toy falsification experiment; **NO-GO** for pure FGW or exact GED as the sole 50-node verifier.
