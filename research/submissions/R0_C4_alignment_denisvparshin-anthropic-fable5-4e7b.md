---
mission: R0-C
run: C4 (independent repeat, REPEAT_CLAIM; blind group R0-C)
contributor: DenisVParshin
agent_or_model: Claude Fable 5 (claude-fable-5), Claude Code CLI
date: 2026-08-31
mission_modified: false
web_research_used: true
independence_disclosure: >
  R0-C1 (PR #30), R0-C2 (merged; file left unopened), and R0-C3 (PR #33)
  were NOT read. Unavoidable exposures: their issue/PR titles ("typed QAP
  verifier", "multi-relational FGW verifier — independent cross-family
  repeat with an executed experiment"), seen during board-state
  determination — the titles reveal that prior runs went QAP- and
  FGW-directions; convergence on those method names must not be counted as
  independent. One grep-surfaced fragment line from R0-C2 (a remark that
  shortest-path structure aligns A-B with A-X-Y-B imperfectly) is a second
  disclosed leak. Same-agent note: one of eight sequential runs by one agent
  in one session; anchored by my own R0-A2 and R0-H2 runs.
---

# Decision

Primary verifier: a **hybrid staged aligner** — (1) build a soft node-affinity
matrix from type compatibility and label-embedding similarity; (2) grow
structurally consistent correspondences with a greedy SME-style matcher
(one-to-one, parallel connectivity, polarity-strict, systematicity-weighted;
see R0-A2); (3) emit the discrete mapping, the matched subsystem, and a
two-channel score (S_rel, S_sem). Fallback/cross-check: **Fused
Gromov-Wasserstein** with multi-restart on the same inputs, used to flag
disagreements and to score global shape when the greedy matcher finds only
fragments. Rejected as primary: exact GED and subgraph isomorphism
(exponential; also GED's edit semantics answers "how many edits apart" — the
wrong question, since two analogous thoughts are *many* edits apart);
spectral matching (assignment quality poor on small sparse typed graphs,
unexplainable); pure QAP solvers (approximations exist — scipy's FAQ — but
produce full permutations, not partial typed correspondences, and ignore
edge types natively). The staged `soft → consistency → discrete` design is
explicitly better than any single algorithm because the three requirements —
soft semantics, hard structural consistency, discrete explainable output —
live at different stages.

# Confidence

HIGH on the staged-hybrid shape and on rejecting exact methods. MEDIUM on
greedy-SME-first versus FGW-first ordering: FGW is the mathematically
stronger global scorer, but it is non-convex, initialization-sensitive,
needs α (structure/feature trade-off) calibrated on labeled pairs that do
not exist yet, and yields soft couplings that still require discretization
before explanation. Main uncertainty: whether greedy alignment's early
commitments degrade badly on noisy extracted graphs — the toy experiment
measures exactly this against planted mappings.

# Answers to the mission's Resolve questions

1. **Primary:** staged greedy typed aligner (above). **Fallback:** FGW
   (POT implementation), 5 restarts (product-marginal init + 4 random),
   entropic regularization, α fixed at 0.5 initially and recalibrated on
   R0-G gold pairs.
2. **Hybrid better than one algorithm?** Yes — see Decision; additionally
   the two components fail differently (greedy: local traps; FGW: mass
   smearing), so disagreement between them is itself a useful low-confidence
   signal.
3. **Input features required:** node type, node label embedding, edge type,
   polarity, ordered argument roles, one-level reified relations,
   core/peripheral status (peripheral elements get 0.5 weight), degrees
   computed internally. Nothing else.
4. **Unmatched nodes:** never penalized structurally (partial matching is
   the norm); reported explicitly in the output as `residue_1`/`residue_2`,
   which doubles as the **complementarity** signal ("where one thought
   continues past the other") and feeds divergence explanations.
5. **Cross-domain analogy without semantic collapse:** yes, by
   construction — semantics enter only as soft seed affinity (a tiebreaker,
   never a constraint); a zero-semantic-similarity seed pair is still
   admissible if type-compatible. The delexicalized S_rel channel carries
   the verdict; S_sem is reported beside it, and the combination weight is
   a visible config value, not a buried constant.
6. **Scoring equation (implementable):**
   `S_rel = Σ_matched λ^depth(r) · w_status(r) / Σ_smaller-graph λ^depth(r)`
   (λ ≈ 1.5, w_status: core 1.0 / peripheral 0.5);
   `S_sem = mean over matched node pairs of cos(label_emb)`;
   `resonance = (S_rel, S_sem, coverage, residues)` — a structured result;
   any scalar for ranking uses `0.7·S_rel + 0.3·S_sem` v0.1, recalibrated
   on the benchmark.
7. **Runtime 50×50, top-20:** greedy aligner — seed generation ~|E1|·|E2| ≈
   4·10⁴ type checks, merge over ≤ a few hundred seeds: single-digit
   milliseconds in Python. FGW 50×50 with 5 restarts: tens to a few hundred
   ms. Top-20 verification with both: well under 5 s total. Corpus size
   irrelevant (verification touches only top-K).
8. **Thought DNA requirements:** exactly R0-A2's list (closed typed
   polarity-signed relations, roles, one-level reification, spans) plus
   label embeddings computable on demand and the core/peripheral flag. The
   verifier adds no new fields — convergent constraint, not coincidence:
   the representation should be shaped by the verifier, and both runs of
   this pipeline stage (A and C) demand the same fields.

# Required Thought DNA / Graph Representation

As above; directed typed multigraph with one-level reification. FGW consumes
a derived view: node feature vectors (type one-hot ⊕ label embedding) and a
shortest-path or adjacency cost matrix — derivable, not stored.

# Invariances

| Transformation | Supported | Partially | Not | Mechanism |
|---|---|---|---|---|
| A paraphrase | X | | | alignment on types/roles; labels soft |
| B vocabulary | X | | | seeds admissible at zero semantic sim |
| C ordering | X | | | order-free matching |
| D irrelevant branches | X | | | unmatched residue unpenalized |
| E partial | X | | | partial mappings first-class |
| F granularity | | X | | known weak point: chain A→X→Y→B vs A→B aligns endpoints only unless R0-D contraction views are supplied; shortest-path costs in FGW blur but do not solve it |
| G sizes | | X | | normalize by smaller graph; FGW needs unbalanced/partial variant beyond ~3:1 size ratio |
| H domain substitution | X | | | the design center |
| I extraction noise | | X | | core/peripheral weighting + FGW cross-check |

# Retrieval vs Verification

**EXPENSIVE VERIFICATION** exclusively. Input: two Thought Graphs + optional
affinity matrix. Output: discrete correspondence mapping (nodes, relations),
matched subsystem, S_rel, S_sem, coverage, residues, and a
`verifier_agreement` flag (greedy vs FGW ranking concordance). The mapping
object is the explanation artifact shown to humans.

# Computational Cost

Above (Q7). Memory trivial. The only scaling risk is pathological graphs
(>300 nodes): cap input size, truncate by peripheral-first dropping.

# Existing Implementations

- **POT (`ot.gromov`, `fused_gromov_wasserstein`)** — mature, maintained,
  the standard OT library; includes entropic and partial variants.
  Dependency risk low. Use for the fallback channel.
- **scipy `quadratic_assignment` (FAQ method)** — mature; evaluated,
  usable as a third opinion on small equal-size cases, not adopted (full
  permutations, no types).
- **networkx `graph_edit_distance` / `similarity`** — correct but
  exponential in practice; usable only ≤ ~15 nodes as a benchmark oracle on
  toy cases, never in the pipeline.
- **Greedy SME-lite** — ~300 lines, hand-written (R0-A2), zero dependency
  risk, full semantic control. This is the deliberate build-vs-buy choice:
  the primary verifier is owned code; the mathematical cross-check is
  library code.

# Minimal Pseudocode

(Greedy aligner pseudocode in R0-A2; the staged wrapper:)

```
def verify(G1, G2):
    A = affinity(G1.nodes, G2.nodes)          # type-compat gate + label cos
    M = greedy_align(G1, G2, A)               # R0-A2, polarity-strict
    f = fgw_score(G1, G2, alpha=0.5, restarts=5)   # POT; soft coupling
    agree = rank_concordant(M.score, f)       # over the candidate batch
    return Result(mapping=M.map, S_rel=M.S_rel, S_sem=M.S_sem,
                  coverage=M.coverage, residues=M.residues,
                  fgw=f, verifier_agreement=agree)
```

# Toy Experiment

≤2h. Take 10 seed graphs (from the R0-G seed set); generate perturbed
copies with **planted ground-truth mappings**: relabel all lexemes
(domain-map), permute order, add 30% padding branches, delete 20% of nodes,
split one node into two (granularity). Run the staged verifier and FGW
alone. Metric: **correspondence accuracy** (fraction of planted node pairs
recovered) and ranking separation vs 10 non-matching distractor graphs.
Decision rules: staged verifier ≥ 0.8 correspondence accuracy on
relabel+permute+padding → adopt; < 0.6 → the greedy component is falsified,
promote FGW to primary and add discretization (Hungarian on the coupling);
granularity-split accuracy is expected to fail (documents the R0-D
dependency, not a surprise).

# Failure Modes

1. Greedy early-commitment on symmetric substructures → wrong branch locks
   in (mitigation: 3 randomized restarts, keep best).
2. FGW mass smearing under size asymmetry → misleading low scores for
   legitimate partial matches (use partial/unbalanced GW beyond 3:1).
3. FGW local minima → score noise across runs (multi-restart, report
   variance; if variance high, distrust FGW channel for that pair).
4. Polarity-blind seeding would align "prevents" with "causes" — polarity
   strictness is non-negotiable (R0-H attack pair 5).
5. Generic-skeleton pairs verify successfully (they ARE structurally
   aligned) → verification cannot fix retrieval-stage false positives;
   commonness discounting must happen upstream (R0-B DF stoplist) or in
   ranking (motif-IDF on the matched subsystem — add to v0.2).
6. α miscalibration in FGW silently converts the verifier into an embedding
   comparator (α→0) — freeze α, ablate on benchmark.
7. Correspondence exists but S_sem ≈ 0 and UI shows a "weak" aggregate —
   scalar fusion hides exactly the cross-domain wins; the structured result
   object is mandatory, the scalar is for ranking only.

# What NOT To Build

Exact GED / MCS / subgraph isomorphism in the pipeline; learned matchers
(GNN-based graph matching — no-training rule, uncalibratable); spectral
assignment as primary; hard semantic gating of seeds; a single fused scalar
as the only output; Hungarian on raw label similarity (that is bipartite
matching of words, not structural alignment — the tempting wrong baseline).

# Architecture Consequences

- The verifier's structured Result object (mapping, S_rel, S_sem, coverage,
  residues, agreement flag) is the canonical resonance record — schema it
  now; UI, benchmark, and explanations all consume it.
- Residues are the complementarity feature for free — route them to the
  complementary-resonance detector rather than discarding.
- Polarity-strict seeding and visible (S_rel, S_sem) separation are hard
  requirements inherited jointly with R0-A2.
- FGW stays a cross-check until α and thresholds are calibrated on R0-G
  gold pairs; verifier_agreement is a shipped confidence signal.
- Granularity (F) is formally delegated to R0-D contraction views; the
  verifier API accepts a *list* of graph views per thought and returns the
  best-scoring pair.
- Input size cap (~300 nodes) with peripheral-first truncation.

# Sources

1. Falkenhainer, Forbus, Gentner — *The Structure-Mapping Engine*, AIJ 1989;
   Forbus & Oblinger 1990 (greedy). The consistency-growth core of the
   primary verifier.
2. Vayer et al. — *Optimal Transport for Structured Data with Application
   on Graphs* (FGW), ICML 2019. The fallback scorer; α semantics.
3. Peyré, Cuturi — *Computational Optimal Transport*, 2019 (and the POT
   documentation, `ot.gromov`). GW/FGW solvers, entropic and partial
   variants, non-convexity and initialization caveats.
4. Xu et al. — *Scalable Gromov-Wasserstein Learning for Graph Partitioning
   and Matching*, NeurIPS 2019. Evidence on GW local minima and restart
   strategies at graph-matching scale.
5. scipy documentation — `optimize.quadratic_assignment` (FAQ algorithm).
   The evaluated-and-not-adopted QAP route.
6. networkx documentation — `graph_edit_distance` and similarity
   algorithms. The evaluated-and-rejected exact route (usable as toy-case
   oracle only).
7. Chalmers, French, Hofstadter — JETAI 1992. Why verifier quality cannot
   exceed representation quality — the standing caveat over all scores.
