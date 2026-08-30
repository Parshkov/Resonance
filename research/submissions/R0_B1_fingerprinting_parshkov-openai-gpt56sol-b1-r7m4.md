---
mission: R0-B
run: R0-B1
contributor: Parshkov
agent_id: parshkov-openai-gpt56sol-b1-r7m4
agent_or_model: OpenAI GPT-5.6 Sol
model_mode: not separately exposed
execution_environment: ChatGPT connected session
date: 2026-08-30
mission_modified: false
web_research_used: true
code_execution_used: true
additional_agents_used: false
blind_constraints_preserved: true
blind_sibling_exposure: none
---

# Decision

**GO** for a Shazam-like retrieval layer, but not as a single whole-graph hash and not as plain WL-set similarity. Use a sparse **Relational Constellation Fingerprint**: multiscale typed-WL landmark descriptors are paired inside a small graph-distance target zone; each pair is hashed together with the typed/directed path relation between the landmarks. Store these hashes in an inverted index, suppress common hashes by document frequency, and rank candidates by the weight of hash collisions that agree on one coherent partial node mapping. This directly transfers Shazam's useful pattern — sparse local features, combinatorial entropy, cheap lookup, then alignment consensus — while keeping cross-domain analogy possible because the primary channel is structural rather than lexical.

# Confidence

**HIGH** that sparse relational pair hashes + inverted postings are the right retrieval architecture for the MVP; **MEDIUM** on the exact descriptor/path quantization. The central risk is the stability/discrimination trade-off: a descriptor rich enough to be rare becomes fragile under graph edits, while a coarse structural descriptor survives edits but produces generic motifs. The design therefore deliberately emits multiple projections/scales and lets corpus document frequency choose useful fingerprints rather than betting on one universal hash.

# Best Algorithm / Method

## 1. Cognitive landmark

A landmark is **not raw text and not necessarily a special semantic concept**. The Thought Graph is already sparse. Every sufficiently confident node with at least one typed relation is a candidate landmark.

For node `v`, compute deterministic descriptors at two scales:

```text
D0(v) = functional_role(v)
D1(v) = H(
  D0(v),
  multiset[(IN|OUT, relation_family(e), D0(u)) for incident neighbors u]
)
```

`D1` is a directed, edge-typed one-round WL-style neighborhood label. A later experiment may add `D2`, but the MVP should not start there: larger WL radii become brittle when nearby nodes are missing.

Generate two projections of relation vocabulary:

- **fine**: canonical edge/relation type;
- **coarse**: relation family such as causal, evidential, constraint, goal/method, intervention.

The coarse projection is intentional error tolerance, not fuzzy hashing.

## 2. Relational fingerprint

For each anchor node `a`, choose up to `F=3` target landmarks `b` inside graph distance 1–3. Prefer deterministic diversity across relation/path families; if there are more candidates, stable-hash tie-breaking avoids ordering dependence.

For each pair, obtain one or two canonical shortest path profiles. A path token records edge direction relative to traversal and relation family. Consecutive identical families may also be collapsed for a coarse granularity projection.

Concrete record before final hashing:

```json
{
  "version": "rcf-v1",
  "projection": "fine|coarse",
  "scale": 0,
  "a_sig": "D0-or-D1-hash",
  "b_sig": "D0-or-D1-hash",
  "path": [["+", "causal"], ["+", "causal"]],
  "distance_bucket": "1|2|3"
}
```

Canonical-serialize and hash to **128 bits** (BLAKE2b-128 is sufficient for the prototype). The inverted posting stores:

```text
hash128 -> (thought_id, anchor_a_local_id, anchor_b_local_id, scale, projection)
```

For a 50-node graph, `F=3`, two scales, and pruning unreachable/duplicate pairs yields roughly **150–300 postings**. At 1M Thoughts this is 150–300M postings: about 1.8–3.6 GB at 12 raw bytes/posting before key/value and database overhead. That is server-scale, not distributed-system scale.

## 3. Entropy and common-motif suppression

Maintain document frequency `df(h)` and weight a collision:

```text
idf(h) = log((N + 1) / (df(h) + 1))
```

Do not read posting lists above a configured `max_df`; initial value: `min(5000, 0.005*N)`, tuned only against the benchmark. If a query has too few surviving hashes, relax the cutoff instead of silently falling back to generic motifs.

This is the direct analogue of Shazam's requirement that fingerprints be reproducible **and sufficiently entropic**. A `problem -> causes -> failure` pattern may be structurally meaningful yet useless as an index key if it occurs everywhere.

## 4. Candidate voting and the graph analogue of time offset

A matching pair hash does more than vote for a Thought. It proposes endpoint correspondences:

```text
(query a -> candidate a')
(query b -> candidate b')
```

Accumulate sparse weights:

```text
M[q_node, c_node] += idf(hash)
raw_score[candidate] += idf(hash)
```

For the best raw candidates, greedily construct a one-to-one partial mapping `pi` from the highest supported `(q_node,c_node)` pairs. Then count only fingerprint collisions whose two endpoint proposals agree with `pi`.

```text
coherent_score =
    sum(idf(h) for collisions consistent with pi)
    / sum(idf(h) for usable query fingerprints)
```

Rank by coherent score, then by number of distinct query landmarks covered. Send only top ~20 to mission C's expensive verifier.

**This partial mapping `pi` is the graph analogue of Shazam's time offset.** A chance hash collision is weak evidence. Many independent pair hashes agreeing on the same node correspondence is strong evidence.

## 5. Optional anchored channel

A second posting family may add a normalized semantic/knowledge bucket to one endpoint for direct/same-domain recall. It must remain a separate channel. Analogical mode must not require it, otherwise battery/organization analogies disappear by design.

MinHash/SimHash/ANN may later sketch the *set* of fingerprints or semantic channel, but they should not be the primary index because they discard the local endpoint correspondence needed for the consensus test.

# Why It Fits Resonance

Shazam's important contribution is not "hashing." Its paper explicitly balances locality, reproducibility, and entropy; pairs sparse peaks to gain combinatorial specificity; and verifies a candidate because many local collisions agree on one temporal alignment. Thought Graphs need the same division of labor.

WL-style labels cheaply encode local topology and node labels, but whole-graph WL kernels answer a different question: aggregate graph similarity. Graphlet counts likewise lose the relative placement of matching motifs. Pairing local descriptors restores that relational geometry while remaining indexable.

The primary fingerprint uses functional roles, typed directions, and path relations rather than concept words. Therefore the hard positive "different words, same structure" can collide, while rewiring the same vocabulary changes pair/path fingerprints. Fine/coarse and radius-0/radius-1 projections intentionally trade discrimination against edit tolerance instead of hiding that trade-off inside one learned embedding.

# Required Thought DNA

Each **node** needs only:

- stable local `id` within the Thought;
- canonical `functional_role` from a small controlled vocabulary;
- extraction `confidence` (used only to exclude very unreliable landmarks);
- optional normalized semantic/knowledge anchor for the secondary channel.

Each **edge** needs:

- `source`, `target`;
- canonical directed `relation_type`;
- a coarser `relation_family` or a deterministic mapping from type to family;
- optional extraction confidence if low-confidence edges are to be projected out.

The fingerprint algorithm does **not** require free text, embeddings, books/resources, timestamps, global node IDs, or an LLM at match time.

# Required Graph Representation

A **directed typed graph** is sufficient. A multigraph is acceptable if Thought DNA later permits several distinct relations between the same nodes; the canonical path serializer must then include edge identity/type. Reified relation nodes can also be fingerprinted as ordinary typed nodes if higher-order relations are required later.

A tree is too restrictive. A hypergraph is not required by this retrieval algorithm.

# Invariances

| Transformation | Supported | Partially | Not Supported | Mechanism |
|---|---:|---:|---:|---|
| A paraphrase | ✓ | | | primary hashes ignore free text |
| B vocabulary substitution | ✓ | | | functional roles + relation structure; semantic channel optional |
| C node ordering | ✓ | | | canonical multisets/path serialization |
| D irrelevant branches | ✓ | | | local fingerprints away from insertion survive; DF suppresses junk |
| E missing nodes | | ✓ | | unaffected local pair hashes survive; coverage decreases |
| F different granularity | | ✓ | | coarse relation-family projection, collapsed repeated paths, distance buckets |
| G different graph sizes | ✓ | | | local target zones; score normalized by usable query weight |
| H domain substitution, structure preserved | ✓ | | | structural channel contains no domain identity |
| I modest extraction mistakes | | ✓ | | multi-scale/fine+coarse redundancy; errors near a landmark still destroy some hashes |

A causal reversal or changed relation type is intentionally **not invariant**.

# Retrieval vs Verification

**FAST RETRIEVAL.**

Index: hash-keyed inverted postings. Query cost is proportional to generated query hashes plus the capped postings actually read, not corpus size.

The cheap coherence step returns a candidate Thought ID, a retrieval score, and a provisional landmark mapping `pi`. It is not final graph alignment. Mission C should independently verify the top candidates and may reject the provisional mapping.

# Computational Cost

For graph `G=(V,E)`, two WL rounds are `O(E)` for fixed rounds. Short target-zone searches to depth 3 are effectively `O(V+E)` on 10–100 node graphs. With fixed fan-out `F`, fingerprint generation is `O(V*F)` after local descriptors.

**50 nodes:** roughly 150–300 postings; milliseconds in Python should be realistic.

**Top 20:** no expensive pairwise graph computation is needed here. Coherence uses sparse collision maps; greedy one-to-one consensus is approximately `O(C log C)` for `C` collision proposals per candidate.

**1M Thoughts:** 150–300M postings. Query performs ~150–300 key lookups. Common posting lists are skipped/capped. Raw posting storage is a few GB; realistic indexed storage is likely several to low tens of GB depending on backend. This is feasible on one machine and falsifiable with a synthetic million-ID index before production data exists.

# Existing Implementations

- **NetworkX 3.6+** — current `weisfeiler_lehman_subgraph_hashes` exposes per-node multiscale hashes and now distinguishes directed in/out neighborhoods. Useful reference/prototype, though Resonance needs custom relation-family/path serialization.
- **GraKeL** — implements WL, graphlet, neighborhood-hash and other kernels. Useful for cross-checking, but the project is kernel/classification-oriented and should not dictate the production posting format.
- **Python `hashlib.blake2b`** — no extra dependency for 128-bit deterministic hashes.
- **LMDB / python-lmdb** — mature ordered key-value store and current Python bindings; suitable for a compact read-heavy hash→postings prototype. SQLite is simpler for early tests but becomes bulky at hundreds of millions of rows.
- **NetworkX/custom code over MinHash/LSH libraries** for v0.1 — the custom algorithm is short enough that an opaque ANN layer is unnecessary until the benchmark proves exact relational postings insufficient.

# Minimal Pseudocode

```text
index(thought):
  D0 = functional_role labels
  D1 = typed_directed_WL_round(D0)

  for scale in [D0, D1]:
    for anchor a with confidence >= threshold and degree(a) > 0:
      targets = choose_up_to_F_nodes_within_3_hops(a, F=3)
      for b in targets:
        for projection in [fine, coarse]:
          path = canonical_path_profile(a, b, projection)
          record = canonical(scale[a], scale[b], path, distance_bucket)
          h = blake2b_128(record)
          emit posting(h, thought_id, a, b, scale, projection)

  update document_frequency per unique h

query(Q):
  q_records = fingerprint(Q)
  votes = {}
  endpoint_support = {}

  for q in q_records:
    if df(q.hash) > max_df: continue
    w = log((N+1)/(df(q.hash)+1))
    for p in postings[q.hash]:
      votes[p.thought] += w
      endpoint_support[p.thought, q.a, p.a] += w
      endpoint_support[p.thought, q.b, p.b] += w

  candidates = top_raw(votes, M=200)
  for c in candidates:
    pi = greedy_one_to_one(endpoint_support[c])
    score[c] = idf_weight_of_collisions_consistent_with(pi) / usable_query_idf

  return top(score, 20), provisional_pi
```

# Toy Experiment

I ran a local Python pilot on a 10-node directed typed causal/goal/evidence graph. Fingerprints used two scales: `D0=functional role` and `D1=typed directed one-hop neighborhood`, then hashed ordered node pairs with a directed relation-family path profile up to three hops.

Pair-hash Jaccard against the original:

| Variant | Combined | D0 only | D1 only |
|---|---:|---:|---:|
| paraphrase all text | 1.000 | 1.000 | 1.000 |
| cross-domain vocabulary substitution | 1.000 | 1.000 | 1.000 |
| add irrelevant 2-node branch | 0.826 | 0.909 | 0.750 |
| delete 2/10 nodes | 0.588 | 0.800 | 0.421 |
| expand one causal edge with an intermediate node | 0.432 | 0.615 | 0.286 |
| same nodes/roles/words, rewire causal structure | **0.167** | 0.340 | **0.033** |

This is not a benchmark result and does not prove the final hash. It demonstrates the intended trade-off: coarse scale survives edits; local WL scale sharply rejects structural rewiring. The design should be falsified if, on the R0 benchmark, the structural positive does not consistently outrank same-vocabulary rewired negatives or if granularity edits destroy recall.

# Failure Modes

1. **Generic causal chains:** thousands of Thoughts emit the same role/path fingerprint; posting lists explode. Mitigation: DF cutoff/IDF, not semantic guesswork.
2. **Role-extraction drift:** `mechanism` becomes `evidence`; all hashes touching that node change. Multi-scale redundancy helps but does not solve bad extraction.
3. **Granularity insertion:** `A→B` vs `A→X→Y→B` breaks D1 neighborhoods and exact path length. Coarse path projection helps only for semantically collapsible relation families.
4. **Symmetric/repeated motifs:** many nodes have identical structural descriptors, so collisions support several incompatible mappings. Consensus coverage must penalize ambiguous endpoint votes.
5. **Structurally analogous but too generic:** two unrelated Thoughts share a common motif and a coherent small mapping. Expensive verification and minimum coverage are still necessary.
6. **Dense cross-links:** shortest-path identity becomes unstable when many equivalent paths exist. Limit to a small canonical path set and test dense graphs separately.
7. **Adversarial same-degree rewiring:** radius-0 hashes remain high while structure changes. Radius-1 pair hashes and the verifier must dominate the decision.
8. **Over-specific semantic anchors:** anchored channel gains precision but silently kills cross-domain analogy if allowed to gate candidate inclusion.

# What NOT To Build

- **One embedding per Thought + cosine** as the primary retrieval identity: loses correspondence and invites topical shortcuts.
- **One whole-graph WL hash:** exact equality is too brittle and gives no partial matching.
- **Graphlet-count vector alone:** counts discard where motifs occur relative to each other.
- **MinHash of the complete fingerprint set as the only index:** useful for resemblance, but destroys anchor correspondence needed for coherent mapping.
- **Learned GNN/graph encoder in R0:** training/data burden, instability and explanation cost are unnecessary before deterministic fingerprints are falsified.
- **Exact subgraph isomorphism/GED during retrieval:** wrong computational stage.
- **Global ontology ingestion or privacy cryptography** inside B1: unrelated to proving the retrieval kernel.

# Architecture Consequences

1. Thought DNA must preserve canonical functional node roles and directed typed relations.
2. Relation types need a deterministic coarse-family projection.
3. Node IDs must be stable within one Thought so collision records can propose correspondences.
4. Fingerprinting must emit multiple scales/projections; no single universal hash is sufficient.
5. Primary analogical fingerprints must not require lexical/domain identity.
6. Every posting retains local endpoint IDs; storing only `hash -> thought_id` throws away the Shazam-style alignment signal.
7. The index must maintain `df(hash)` and skip/cap common motifs.
8. Retrieval output includes a provisional partial mapping and coverage, not only a scalar score.
9. Granularity tolerance belongs partly in path canonicalization and partly in later verification; B1 should not pretend to solve it completely.
10. Benchmark G must explicitly compare different-words/same-structure against same-words/rewired-structure and report fingerprint survival by transformation.

# Sources

1. **Avery Wang (2003), “An Industrial-Strength Audio Search Algorithm.”** https://www.princeton.edu/~cuff/ele301/files/Wang03-shazam.pdf — primary source for sparse landmarks, combinatorial pair hashing, entropy/robustness trade-off, inverted lookup, and alignment-consensus scoring.
2. **Shervashidze et al. (2011), “Weisfeiler-Lehman Graph Kernels,” JMLR.** https://jmlr.org/papers/v12/shervashidze11a.html — primary basis for fast multiscale local structural labels; runtime linear in edges times WL rounds.
3. **Hido & Kashima (2009), “A Linear-Time Graph Kernel,” ICDM.** https://research.ibm.com/publications/a-linear-time-graph-kernel — independent precedent for hashing node neighborhoods with linear graph-time complexity.
4. **Shervashidze et al. (2009), “Efficient Graphlet Kernels for Large Graph Comparison,” AISTATS.** https://proceedings.mlr.press/v5/shervashidze09a.html — establishes small-subgraph features and the cost/sampling trade-off; useful baseline but not enough alignment information.
5. **Kondor, Shervashidze & Borgwardt (2009), “The Graphlet Spectrum,” ICML.** https://doi.org/10.1145/1553374.1553443 — explicitly identifies loss of relative position as a limitation of simple subgraph-count kernels, motivating relational pairing.
6. **Broder (1997), “On the Resemblance and Containment of Documents.”** https://www.cs.princeton.edu/courses/archive/spring13/cos598C/broder97resemblance.pdf — primary MinHash/set-sketch precedent; useful as a fallback sketch but insufficient for endpoint alignment.
7. **Morris et al. (2016), “Faster Kernels for Graphs with Continuous Attributes via Hashing.”** https://arxiv.org/abs/1610.00064 — shows continuous graph attributes can be discretized through randomized hashing before discrete graph kernels; relevant if a future semantic channel needs soft buckets.
8. **NetworkX 3.6.1 WL subgraph hashing documentation.** https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.graph_hashing.weisfeiler_lehman_subgraph_hashes.html — authoritative implementation reference for per-node multiscale WL hashes and directed in/out handling.

**Final recommendation: GO.** Build the deterministic relational inverted-index prototype first; let the transformation benchmark decide whether additional fuzzy/semantic retrieval is necessary.
