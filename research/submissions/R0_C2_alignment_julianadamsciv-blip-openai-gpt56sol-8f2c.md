---
mission: R0-C
run: R0-C2
contributor: julianadamsciv-blip
agent_id: julianadamsciv-blip-openai-gpt56sol-8f2c
agent_or_model: OpenAI GPT-5.6 Sol
model_mode: reasoning
execution_environment: ChatGPT chat with GitHub connector
web_research_used: true
code_execution_used: false
external_tools_used: GitHub connector; web search
additional_agents_used: false
mission_modified: false
blind_constraints_preserved: true
blind_exposure: none; R0-C1 issue/submission was not inspected
date: 2026-08-30
---

# Decision

**GO: use Partial Fused Gromov-Wasserstein (pFGW) as the primary expensive verifier, then convert its soft transport plan into an explicit partial node mapping and rescore that mapping with typed directed-edge consistency.** Use multi-start initialization and evaluate several transported-mass fractions. The fallback is **FAQ-style quadratic assignment** on a padded/selected candidate subgraph when graphs are near equal size or when a hard one-to-one structure-first match is desired. Do not make exact Graph Edit Distance, maximum common subgraph, or exact subgraph isomorphism the default verifier.

# Confidence

**MEDIUM-HIGH.** FGW is unusually well matched to Resonance because it jointly optimizes feature and relational agreement and exposes a coupling matrix, while partial FGW permits unmatched mass. The main uncertainty is how best to encode a directed typed Thought Graph into intra-graph structural cost matrices without losing edge direction/type; vanilla metric FGW was developed primarily for structured objects with symmetric relational costs. This must be tested empirically before Thought DNA is frozen.

# Best Algorithm / Method

For graphs `G=(V,E)` and `H=(W,F)`, construct:

- node feature cost `M_ij` from role/type compatibility plus normalized semantic dissimilarity;
- one or more intra-graph structural matrices `C_G`, `C_H` derived from typed directed shortest-path / relation distances;
- node masses `p,q` (uniform for MVP, optionally confidence-weighted later).

Solve partial FGW over coupling `T >= 0` with transported mass `m`:

`min_T (1-alpha) * <M,T> + alpha * sum_ijkl L(C_G[i,k], C_H[j,l]) T[i,j]T[k,l]`

subject to partial-mass constraints (`T1 <= p`, `T^T1 <= q`, total transported mass `m`). This combines feature agreement and relational distortion while leaving some nodes unmatched. POT already implements partial (fused) GW-family solvers; its GW solvers use conditional-gradient style optimization and return the transport/coupling plan.

Run `m` over a small grid, e.g. `{0.4,0.6,0.8,1.0} * min(total mass)`, and `alpha` over `{0.6,0.8}`. Use 3-5 initializations. For each plan, extract a discrete partial one-to-one mapping by Hungarian assignment on `-T` after dropping rows/columns whose transported mass is below threshold.

Then compute a Resonance score on that mapping:

`S = 0.25*N + 0.50*R + 0.15*C + 0.10*Q - 0.15*U`

where:
- `N` = mean mapped node compatibility in `[0,1]`;
- `R` = weighted fraction of mapped typed relations whose type and endpoints correspond;
- `C` = directed causal/path-order consistency;
- `Q` = coverage = `2|mapping|/(|V|+|W|)`;
- `U` = contradiction penalty for mapped pairs with incompatible semantic/role constraints.

The coefficients are MVP priors, not learned truth; calibrate them on R0-G benchmark data.

**Fallback:** FAQ/QAP (SciPy `quadratic_assignment(method="faq")`) on square adjacency/compatibility matrices, with dummy nodes or a candidate induced subgraph. FAQ gives an explicit permutation and is cubic per iteration in the original formulation, but it is fundamentally a full matching objective and therefore less natural for partial/noisy graph overlap.

# Why It Fits Resonance

pFGW directly addresses the mission's difficult combination: unequal sizes, soft node similarity, structural importance, partial correspondence, and a need for an actual mapping. FGW was designed to combine feature and structural costs; partial GW relaxes full-mass matching; recent work formulates subgraph matching itself as partial FGW and reports robustness to noise. The coupling is also inspectable, so Resonance can explain which branches correspond instead of returning only a scalar.

Cross-domain analogy remains possible because `alpha` can emphasize relational structure while node cost uses **functional role/type** and only lightly uses domain-specific semantics. Semantic embeddings must not dominate the cost matrix; otherwise analogies collapse into topical similarity.

# Required Thought DNA

Node fields actually required:

1. `node_id` — stable graph-local identity.
2. `node_role` — problem / goal / mechanism / constraint / evidence / method / outcome (or equivalent compact role ontology).
3. `concept_normalized` — canonical concept label or embedding input.
4. `semantic_vector` or reproducible semantic-distance handle — used only for soft node cost.
5. `confidence` — optional node mass/penalty weight; MVP may set all to 1.

Edge fields actually required:

1. `source`, `target` — direction is essential.
2. `relation_type` — e.g. causes, enables, constrains, supports, contradicts, requires.
3. `confidence/weight` — optional; default 1.

Do not add provenance or timestamps to the matching kernel unless experiments show they improve matching; they can remain external metadata.

# Required Graph Representation

**Directed typed property graph.** A tree is too restrictive; a hypergraph is not justified for MVP complexity. For pFGW, compile the property graph into numerical structural matrices. Preserve direction/type in the source graph even if one experimental cost matrix is symmetric. For MVP, use relation-type-specific directed shortest-path matrices and/or a weighted aggregate; compare this against a simpler symmetrized baseline in the toy experiment.

# Invariances

| Transformation | Supported | Partially | Not Supported | Mechanism |
|---|---:|---:|---:|---|
| A paraphrase | X | | | normalized/embedded node cost |
| B vocabulary substitution | | X | | role + soft semantics; structure carries weight |
| C node ordering | X | | | graph/coupling objective is permutation-invariant |
| D irrelevant branches | | X | | partial transported mass leaves nodes unmatched |
| E missing nodes | | X | | partial matching + relational distortion tolerance |
| F different granularity | | X | | shortest-path structure can align A-B with A-X-Y-B imperfectly |
| G different graph sizes | X | | | rectangular partial coupling |
| H domain substitution preserving structure | | X | | high structural weight + role compatibility; semantics can still interfere |
| I modest extraction mistakes | | X | | soft costs, partial mass, multi-start; wrong relation types still hurt |

# Retrieval vs Verification

**EXPENSIVE VERIFICATION.** Inputs are two candidate Thought Graphs plus normalized node/edge features. Output is `(score, soft coupling T, discrete partial mapping, unmatched nodes, matched relations, divergence explanation)`.

Do not run pFGW over the corpus. The fast retrieval stage should reduce 1M thoughts to roughly top-20 candidates first.

# Computational Cost

Dense GW/FGW objectives involve pairwise structural terms and non-convex optimization; practical conditional-gradient implementations repeatedly manipulate `n x m` couplings and structural matrices. For 50x50 graphs, this is entirely plausible as a verifier, especially with top-K=20, but should be benchmarked rather than assumed.

MVP target: keep one 50x50 pFGW solve comfortably sub-second to low-single-digit seconds on CPU; 20 candidates with several `(m,alpha)` settings can otherwise multiply into tens of seconds. Use early stopping, warm starts, and a coarse-first parameter grid. If runtime misses target, first reduce restarts/grid size; second use FAQ or a sparse candidate-pair mask; do not weaken retrieval scalability by moving FGW upstream.

FAQ's published implementation has cubic scaling in vertex count and SciPy exposes a maintained approximation. Exact GED is NP-hard and NetworkX warns it may be slow; therefore reserve GED for tiny benchmark diagnostics, not production verification.

# Existing Implementations

- **POT (Python Optimal Transport)** — `ot.gromov.fused_gromov_wasserstein`, `partial_gromov_wasserstein`, and current partial-FGW support. Mature Python library; best MVP starting point. Risk: non-convex local minima and API movement across versions.
- **SciPy** — `scipy.optimize.quadratic_assignment(method="faq")`. Mature fallback with seeds/initialization support; square-matrix/full-match bias.
- **NetworkX** — GED/edit-path implementations useful as tiny-graph baselines. Risk: exact/near-exact search becomes slow quickly.
- **PGW_Metric** reference code (Bai et al., ICLR 2025) — useful independent check of modern partial-GW formulations; less mature than POT.

# Minimal Pseudocode

```python
def verify(G, H):
    M = node_cost_matrix(G, H)          # role + soft semantic cost
    CG = structural_cost(G)             # directed/typed path structure
    CH = structural_cost(H)
    best = None
    for mass_frac in [0.4, 0.6, 0.8, 1.0]:
        for alpha in [0.6, 0.8]:
            for seed in range(3):
                T = partial_fgw(CG, CH, M, mass_frac, alpha, seed)
                pairs = hungarian_on_transport(T, min_mass=0.02)
                score = resonance_score(G, H, pairs, T)
                best = max(best, (score, pairs, T), key=lambda x: x[0])
    return best
```

# Toy Experiment

Implement in <=2 hours with 12 synthetic graph pairs, each 20-40 nodes:

1. Four positives generated from one latent directed typed graph under paraphrase/domain relabeling, 20% node deletion, 20% irrelevant branches, and one edge-splitting granularity change.
2. Four hard negatives using the **same vocabulary** but rewired causal/typed edges.
3. Four unrelated controls.

Compare: cosine-of-whole-text baseline, FAQ, FGW full-mass, pFGW, and pFGW with structural rescoring.

Metrics: AUROC over pair class plus node-mapping F1 against known latent correspondences. **Falsification threshold:** reject the recommendation if pFGW+rescore fails to beat the semantic baseline and FAQ by >=0.10 mapping-F1 on cross-domain positives, or if it cannot keep same-words/rewired negatives below positives by a clear margin.

# Failure Modes

1. Two regular graphs with similar distance spectra but opposite causal semantics can receive high structural agreement.
2. Semantic embeddings can force same-topic wrong-role nodes together and drag the coupling into a bad local optimum.
3. A long causal chain versus a compressed single edge may remain too costly despite intended granularity tolerance.
4. Repeated motifs create ambiguous many-to-many transport; Hungarian discretization may choose an arbitrary branch.
5. Wrong extraction of one high-centrality edge can distort many shortest-path entries.
6. Dense graphs collapse shortest-path distances and reduce structural discriminability.
7. Very small true overlap can be gamed by choosing too-low transported mass; coverage term and minimum-mass policy are necessary.

# What NOT To Build

- **Exact GED/MCS as primary verifier:** combinatorial cost and brittle dependence on edit-cost design.
- **Pure subgraph isomorphism:** rejects approximate/noisy/soft matches by definition.
- **Whole-graph embedding cosine:** cannot reliably separate same-words/different-structure from different-words/same-structure.
- **End-to-end GNN matcher:** violates the no-new-large-model/MVP constraint and weakens reproducibility/explainability.
- **Pure GW with no node features:** may align structurally similar but functionally incompatible nodes.
- **Pure semantic OT:** ignores the project's defining relational signal.

# Architecture Consequences

1. Preserve directed typed edges in Thought DNA.
2. Preserve compact functional node roles separate from free-text semantics.
3. Matching API must allow unmatched nodes and return correspondences, not only distance.
4. Structural cost construction is a first-class configurable component.
5. Keep semantic and structural contributions separately inspectable.
6. Benchmark transported-mass fraction rather than fixing full mass.
7. Store confidence so future runs can downweight uncertain extraction.
8. Include same-words/rewired hard negatives in R0-G.
9. Include cross-domain latent-isomorphism positives in R0-G.
10. Do not freeze graph schema until directed/type-aware structural encodings are compared empirically.

# Sources

1. Vayer et al., **Fused Gromov-Wasserstein Distance for Structured Objects** (Algorithms, 2020), https://doi.org/10.3390/a13090212 — formal basis for jointly optimizing feature and structural correspondence; coupling is interpretable.
2. Vayer et al., **Optimal Transport for structured data with application on graphs** / FGW work, arXiv:1811.02834 — original FGW development and graph motivation.
3. POT documentation, **Gromov-Wasserstein and extensions**, https://pythonot.github.io/user_guide.html — authoritative implementation behavior and solver availability for GW/FGW.
4. POT documentation, **ot.gromov partial solvers**, https://pythonot.github.io/master/gen_modules/ot.gromov.html — partial-GW constraints and conditional-gradient implementation; current partial-FGW family support.
5. Pan, Haasler, Frossard, **Subgraph Matching via Partial Optimal Transport**, arXiv:2406.19767 — directly motivates partial FGW for noisy subgraph matching.
6. Bai et al., **Partial Gromov-Wasserstein Metric**, ICLR 2025 / arXiv:2402.03664 — modern theoretical and algorithmic treatment of partial GW.
7. Vogelstein et al., **Fast Approximate Quadratic Programming for Graph Matching**, PLOS ONE 2015, https://doi.org/10.1371/journal.pone.0121002 — FAQ fallback; approximate graph matching via relaxed QAP with cubic empirical scaling.
8. SciPy documentation, **quadratic_assignment(method='faq')**, https://docs.scipy.org/doc/scipy/reference/optimize.qap-faq.html — maintained FAQ implementation, seeds and initialization details.
9. Fishkind et al., **Seeded graph matching**, Pattern Recognition 87 (2019), https://doi.org/10.1016/j.patcog.2018.09.014 — extensions for seeded/differently-sized matching and explicit node alignment.
10. NetworkX documentation, **Similarity Measures / Graph Edit Distance**, https://networkx.org/documentation/stable/reference/algorithms/similarity.html — authoritative practical warning that exact GED is NP-hard/slow and useful mainly as a baseline here.

**GO**, conditional on the toy experiment validating a direction/type-aware structural cost. If pFGW cannot distinguish rewired hard negatives from latent cross-domain analogies, the project should not compensate by adding more semantics; it should revisit the structural representation.