---
mission: R0-D
run: R0-D
contributor: Andy82
agent_id: andy82-openai-gpt56sol-01a05419
agent_or_model: OpenAI GPT-5.6 Sol (medium reasoning)
execution_environment: Codex on macOS
date: 2026-08-30
mission_modified: false
web_research_used: true
code_execution_used: true
additional_agents_used: false
blind_run: false
---

### Decision

**GO** on a two-layer MVP: (1) derive, but never overwrite, a graph view that
suppresses only *transparent directed chain nodes* under explicit semantic and
relation-composition guards; then (2) compare an expected edge with a bounded
typed path in the verifier. Emit coarse typed path fingerprints from both the
original and derived views for retrieval. Do not promise general scale
invariance: `A -> B` and `A -> X -> Y -> B` are equivalent only when `X,Y` add
no branch, polarity, modality, evidence, constraint, or independently useful
mechanism. Multiradius WL can be an auxiliary retrieval feature, not the
invariance mechanism. Defer heat kernels, generic spectral coarsening, and
persistent homology until this cheaper proposal fails a subdivision benchmark.

### Confidence

**MEDIUM-HIGH.** Degree-2 suppression is exactly targeted at edge subdivision,
and bounded paths preserve an explanation mapping. The main uncertainty is not
the graph algorithm but whether extraction can reliably distinguish a
transparent linguistic elaboration from a meaningful causal mediator. The toy
experiment must therefore measure false contractions, not only retrieval
recall.

### Best Algorithm / Method

Keep canonical graph `G` unchanged and derive `G_c`.

**Guarded directed-chain suppression.** A node `v` is suppressible only if:

1. it has one supported incoming and one supported outgoing edge in the active
   causal/relational layer;
2. it is not a branch, merge, root, goal, constraint, evidence, negation,
   modality, temporal boundary, or provenance anchor;
3. it is marked `atomic=false` (the extractor asserts it is an elaboration),
   and its semantic salience is below a fixed threshold;
4. the two directed edge labels, polarity, and modality are compatible under a
   small, audited relation-composition table.

Replace `u -r1-> v -r2-> w` in the derived view with
`u -compose(r1,r2)-> w`. Store `realizes_path=[u,v,w]`, original edge IDs, and
the minimum confidence; repeat to a maximum chain length `L_c` (initially 3).
This is typed suppression of an in-degree-1/out-degree-1 vertex, not arbitrary
node contraction. Suppressing degree-2 vertices is the standard inverse of
edge subdivision; arbitrary contraction has much weaker semantics.

**Retrieval fingerprints.** From both `G` and `G_c`, enumerate directed simple
paths of length 1–3 between non-suppressible anchors. Emit two channels:

```text
structural = H(src_role, composed_relation, dst_role, length_bucket)
semantic   = H(src_concept_bucket, composed_relation, dst_concept_bucket)
```

Use buckets `{1, 2, 3+}` and IDF-weighted inverted postings. Structural tokens
preserve cross-domain recall; semantic tokens reduce collisions. Optionally add
WL subtree tokens for iterations 0–2 on `G_c`. WL refinement is linear in
edges per iteration, but exact neighborhoods change when an edge is subdivided,
so unioning radii improves recall without creating invariance.

**Verification.** After anchor candidates are proposed by role plus semantic
affinity, score each edge `(u,r,w)` in the smaller/coarser view against directed
paths of length `<=4` between candidate endpoints in the other view:

```text
cost = endpoint_cost
     + relation_composition_cost(r, path_relations)
     + 0.15 * transparent_intermediate_count
     + meaningful_intermediate_penalty
     + polarity_or_direction_violation
```

Polarity or direction mismatch is normally a hard rejection. Return the
edge-to-path mapping and the unsuppressed original nodes as the explanation.
This is bounded local matching, not unrestricted graph edit distance.

### Why It Fits Resonance

- It directly handles the named transformation rather than hoping a global
  descriptor becomes subdivision-invariant.
- Both layers are deterministic, inspectable, and model-independent after
  extraction.
- The original graph and provenance survive; every shortcut expands back into
  human-readable correspondences.
- Retrieval uses hashable sparse tokens and ordinary inverted indexes.
- Expensive edge-to-path work is limited to top-K candidates and graphs of
  10–100 nodes.
- It refuses false invariance when an intermediate node changes reasoning.

### Required Thought DNA

**Node fields actually consumed**

- stable `node_id`;
- normalized `role` (mechanism, outcome, goal, constraint, evidence, etc.);
- normalized concept label or embedding bucket for endpoint affinity;
- `atomic` boolean: whether deleting the node would remove a separately
  assertable proposition;
- `polarity` and `modality` when carried by the node;
- `salience` used only by the suppression guard;
- provenance IDs so a derived shortcut can expand to source statements.

**Edge fields actually consumed**

- stable `edge_id`, direction, and normalized `relation_type`;
- polarity and modality;
- confidence;
- provenance IDs.

**Schema-level requirement**

- a versioned, partial relation-composition table. Unknown combinations do not
  compose. `causes ∘ causes -> causal_chain` may be allowed; `enables ∘ causes`
  must remain distinct unless benchmark evidence licenses a rule.

Do not store one universal `contractible=true` truth: suppressibility depends
on the active relation layer and neighboring edges. Store `atomic` and derive
contractibility deterministically.

### Required Graph Representation

A **directed property multigraph**. Direction, typed parallel relations, and
edge provenance matter. The canonical object remains the detailed multigraph;
coarse graphs and shortcut edges are derived views with reversible mappings.
A tree cannot represent merges, feedback, or multiple relation types. A
hypergraph is not required by this method; reify an n-ary relation only if a
separate mission proves it necessary.

### Invariances

| Transformation | Supported | Partially | Not Supported | Mechanism |
|---|:---:|:---:|:---:|---|
| A. paraphrase | | X | | normalized roles/concepts, outside core graph method |
| B. vocabulary substitution | | X | | structural token channel; semantic endpoint affinity may weaken |
| C. node ordering | X | | | graph traversal and hashes ignore serialization order |
| D. irrelevant branches | | X | | local paths, IDF, and partial verifier score; hubs can still pollute |
| E. missing nodes | | X | | edge-to-path/local partial matching, not arbitrary missing anchors |
| F. different granularity | | X | | exact for guarded transparent subdivisions; scored otherwise |
| G. different graph sizes | | X | | normalized local feature overlap and partial mapping |
| H. domain substitution | | X | | role/relation-only channel; requires normalized relation types |
| I. modest extraction mistakes | | X | | redundant original/coarse views; hard direction/polarity errors remain |

No method should treat insertion of a meaningful mediator, new branch,
reversed edge, or changed modality as invariant.

### Retrieval vs Verification

**BOTH, with separate responsibilities.** Retrieval indexes original-view and
coarse-view path hashes (plus optional WL tokens) in IDF-weighted inverted
postings. It aims for recall and does not declare equivalence. Verification
receives candidate anchor affinities and produces an explicit mapping of coarse
edges to detailed paths, their composed relation, penalties, unmatched
branches, and original provenance.

### Computational Cost

Let `n=|V|`, `m=|E|`, path cutoff `L<=4`, and average branching `d`.

- Suppression is `O(n+m)` per pass; with a queue of newly eligible nodes it is
  `O(n+m)` overall for bounded chains.
- Bounded fingerprints are `O(a*d^L)` for `a` anchors, with a hard per-anchor
  cap; bounded BFS is at most `O(a(n+m))`.
- Optional WL for `h=2` is `O(hm)`.
- Verification enumerates bounded paths only between candidate endpoints,
  approximately `O(q*d^L)` for `q` proposed edge correspondences; an optional
  anchor assignment is `O(n^3)`.

For 50 vs 50 sparse graphs (`m≈100`, `d≈2–3`), preprocessing produces at most a
few thousand path tokens and verification should be millisecond-to-low-second
Python work, to be benchmarked rather than asserted as an SLA. Twenty
comparisons remain comfortably inside interactive use without full GED or
eigendecomposition.

For 1M thoughts, cap at 64 structural and 64 semantic tokens per thought:
128M postings. At roughly 8–16 bytes per compressed/uncompressed posting this
is about 1–2 GB before dictionary and serving overhead. Query cost is postings
read plus top-K accumulation, not corpus-wide graph comparison.

### Existing Implementations

- **NetworkX 3.6.x**: mature BSD Python baseline; supports directed shortest
  paths, cutoff traversal, node contraction, and quotient graphs. Its generic
  contraction must be wrapped to preserve typed paths and guards. It is ideal
  for the two-hour experiment, not necessarily the million-item serving path.
- **GraKeL 0.1.10**: scikit-learn-compatible WL and shortest-path baselines.
  Useful for falsification, but the latest PyPI release is from 2023 and wheels
  stop at CPython 3.11; do not make it a production dependency.
- **NetLSD 1.0.2**: reference heat-trace implementation, but PyPI labels it
  alpha and its last release was in 2018. Use only as an experimental global
  baseline.
- Production fingerprints require little more than a custom deterministic
  enumerator plus a standard inverted index; this is safer than adapting a
  graph-kernel package to typed directed multigraph semantics.

### Minimal Pseudocode

```python
def derive_coarse_view(G, max_chain=3):
    C = G.copy()
    for v in queue(C.nodes):
        if not transparent(v, C):
            continue
        (u, e1), (e2, w) = sole_in_out(v, C)
        r = COMPOSE.get((e1.type, e2.type))
        if r is None or not compatible(e1, v, e2):
            continue
        C.add_edge(u, w, type=r,
                   realizes_path=expand(e1) + [v] + expand(e2),
                   confidence=min(e1.confidence, e2.confidence),
                   provenance=e1.provenance + e2.provenance)
        C.remove_node(v)          # only in derived C; G is untouched
    return C

def fingerprints(G):
    views = [G, derive_coarse_view(G)]
    out = set()
    for V in views:
        for a in anchors(V):
            for path in directed_paths(V, a, cutoff=3, cap=64):
                b = path[-1]
                rel = compose_or_sequence(edge_types(path))
                out.add(hash((a.role, rel, b.role, bucket(len(path)))))
    return idf_weight(out)

def verify(coarse, detailed, anchor_candidates):
    mappings = []
    for (u, r, w) in coarse.edges:
        best = min_cost_compatible_path(
            detailed, anchor_candidates[u], anchor_candidates[w], r, cutoff=4)
        mappings.append((u, r, w, best.nodes, best.cost))
    return normalized_score(mappings), mappings
```

### Toy Experiment

Implement in NetworkX in <=2 hours.

1. Create 40 base directed typed graphs (20–50 nodes): causal chains, forks,
   merges, and two hard negatives sharing labels but reversing structure.
2. Positive transforms: subdivide 25%, 50%, and 75% of causal edges with 1–3
   nodes marked `atomic=false`; also paraphrase endpoint labels.
3. Negative transforms: insert `atomic=true` mediators, inhibitory nodes,
   constraints, polarity flips, and side branches.
4. Compare: (B0) single-view WL h=2; (B1) multiradius WL h=0..3;
   (P) guarded suppression + typed path fingerprints + edge-to-path verifier.
5. Report positive-pair ROC-AUC, hard-negative false-positive rate, retrieval
   Recall@20, correspondence precision, and false-contraction count.

Expected: P keeps Recall@20 >=0.90 through 50% transparent subdivision while
hard-negative FPR stays <=0.10 and false contractions are zero. **Falsify the
recommendation** if P improves Recall@20 by <0.10 over B1, contracts any marked
meaningful node, or raises hard-negative FPR by >0.05. Then test a learned or
spectral alternative only against the recorded failure.

### Failure Modes

1. `drug -> insulin -> glucose` is collapsed although insulin is the mechanism
   a user needs to see.
2. `A causes X`, `X inhibits B` is composed into `A causes B` by an unsound
   relation table.
3. A diamond `A -> X,Y -> B` is mistaken for one transparent chain, erasing
   redundancy or alternative mechanisms.
4. A feedback cycle is shortcut repeatedly and creates spurious self-causation.
5. `A may cause X causes B` loses modality through minimum-confidence alone.
6. Two parallel paths with different provenance collapse to one edge and hide
   disagreement.
7. A high-frequency generic relation creates enormous postings and false
   cross-domain candidates.
8. The extractor marks a meaningful constraint `budget` as `atomic=false`;
   structural guards cannot repair a semantic extraction error.

### What NOT To Build

- **No generic graph coarsener.** Spectral/cut preservation solves a different
  problem and can merge semantically distinct thought nodes.
- **No NetLSD/heat-kernel decision rule.** A compact global heat trace is useful
  as a baseline, but it does not return edge-to-path correspondence; full
  eigendecomposition is `O(n^3)` and discards typed direction in the usual
  Laplacian construction.
- **No persistent homology for MVP.** It needs a defensible filtration and
  summarizes cycles/components rather than causal relation composition.
- **No all-pairs full shortest-path kernel in production retrieval.** Classic
  Floyd transformation is cubic and exact path length remains subdivision
  sensitive.
- **No unrestricted transitive closure.** It turns every causal reachability
  into an edge and destroys distance, mechanism, and explanation.
- **No learned GNN coarsener or full graph edit distance.** Training violates
  constraints; unrestricted matching spends complexity before top-K and is
  difficult to reproduce.

### Architecture Consequences

1. Preserve the detailed directed property multigraph as canonical.
2. Make coarse views deterministic, versioned, reversible, and disposable.
3. Add `atomic`, role, polarity, modality, confidence, and provenance fields.
4. Define a small audited relation-composition table; unknown means no merge.
5. Store shortcut-to-original-path mappings for explanations.
6. Index structural and semantic fingerprints as separate channels.
7. Cap path length, tokens per anchor, and high-frequency postings.
8. Put broad granularity tolerance in verification, not only retrieval.
9. Benchmark false contractions as a first-class safety metric.
10. Treat scale invariance as typed and conditional, never universal.

### Sources

1. [Shervashidze et al., “Weisfeiler-Lehman Graph Kernels,” JMLR 2011](https://www.jmlr.org/papers/v12/shervashidze11a.html) — establishes efficient multiradius neighborhood refinement and its `O(hm)`-style linear edge scaling; it supports WL as a cheap auxiliary, not subdivision invariance.
2. [Borgwardt & Kriegel, “Shortest-Path Kernels on Graphs,” ICDM 2005](https://www.dbs.ifi.lmu.de/~borgward/papers/BorKri05.pdf) — primary basis for path-derived graph features and the cubic Floyd transformation used as a baseline warning.
3. [Tsitsulin et al., “NetLSD: Hearing the Shape of a Graph,” KDD 2018](https://cs.au.dk/~karras/netlsd.pdf) — defines multiscale heat-trace signatures and states full eigendecomposition costs `O(n^3)` time and `Theta(n^2)` memory; useful baseline but global rather than explanatory.
4. [Loukas, “Graph Reduction with Spectral and Cut Guarantees,” JMLR 2019](https://www.jmlr.org/beta/papers/v20/18-680.html) — shows what principled generic coarsening preserves (spectral/cut properties), clarifying why that guarantee is not semantic causal preservation.
5. [Robertson et al., “Graph Minor Hierarchies,” Discrete Applied Mathematics 2005](https://doi.org/10.1016/j.dam.2004.01.010) — explicitly relates subdivision and suppression of degree-2 vertices, the graph-theoretic core of the proposed guarded operation.
6. [NetworkX shortest-path documentation](https://networkx.org/documentation/stable/reference/algorithms/shortest_paths.html) — authoritative implementation surface for cutoff BFS/Dijkstra on directed graphs used in the toy verifier.
7. [NetworkX contraction implementation](https://networkx.org/documentation/stable/_modules/networkx/algorithms/minors/contraction.html) — authoritative prototype support for contraction and quotient graphs; its generic semantics motivate a typed wrapper.
8. [GraKeL package and kernel inventory](https://pypi.org/project/GraKeL/) — immediately runnable WL and shortest-path baselines, with current release/platform metadata and dependency risk.
9. [NetLSD reference implementation](https://github.com/xgfs/NetLSD) — reproducible heat-signature baseline; its package age and global-vector API reinforce keeping it experimental.
