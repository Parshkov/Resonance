---
mission: R0-B
run: B2
contributor: dima2010
agent_or_model: Anthropic Claude Opus 5 (claude-opus-5), Claude Code CLI, high-effort mode
date: 2026-08-31
mission_modified: false
web_research_used: true
blind_constraints_preserved: true
agent_id: dima2010-anthropic-opus5-f5ae
---

# Decision

**QUALIFIED GO.** A Shazam-style sparse fingerprint layer is the right shape for Resonance's retrieval
stage, but the naive port fails on an entropy budget that Wang's own paper makes explicit. Shazam works
because pairing two 10-bit spectral peaks with a 10-bit time delta buys a **30-bit** key, giving ~10⁹
buckets against ~10⁹ stored hashes. A Thought-Graph fingerprint that is deliberately **free of surface
vocabulary** — which is exactly what cross-domain analogy (invariance H) requires — has only **~15 bits**,
because its entropy comes from a small closed relation vocabulary and a handful of role classes. At 10⁶
thoughts that is ~6,000 postings per key on average and far worse in the Zipfian tail: not an index, a
scan. My recommendation is therefore a **two-channel fingerprint with two different index mechanics**:
a high-entropy *semantic* channel (~30 bits) that is a genuine Shazam-style exact-hash index and carries
paraphrase/near-duplicate retrieval, and a low-entropy *structural* channel (~15 bits) that must be run as
an **idf-weighted, stop-motif-pruned inverted index in the Video-Google/Philbin tradition**, plus a
tail-only **rare-triple** index (~22 bits) for cross-shard structural long shots. Both channels vote into
a single **correspondence-consistency** test — the graph analogue of Shazam's time-offset histogram — and
retrieval hands the verifier not just candidate IDs but **seed node correspondences**. Keeping the two
channels *unblended* is what makes the project's hard negative ("same words, different structure" vs
"different words, same structure") decidable at all.

# Confidence

**MEDIUM.**

The semantic channel is HIGH confidence and buildable in the MVP budget. The structural channel is the
uncertainty: I am reasoning from an entropy/skew argument and from the empirical distribution I *expect*
thought graphs to have (overwhelmingly short causal chains), not from a measured corpus. If real Thought
Graphs turn out to carry richer relational variety than I assume, the structural channel gains bits and
becomes a real index; if they are as motif-poor as I expect, cross-domain retrieval is only affordable
inside bounded shards. The toy experiment below is designed to settle exactly this, and can return NO-GO
for the structural channel alone without invalidating the rest.

# Best Algorithm / Method

## The three primitives

**1. Cognitive Landmark.** A landmark is *not* a salient word — it is **a node in a relational role**.
Shazam picks spectral peaks because peaks survive codec compression; the analogue is nodes that survive
paraphrase and re-extraction. Selection rule, in order:

- Restrict to nodes incident to at least one edge from the **closed relation vocabulary** (below).
- Score `sal(v) = w₁·causal_betweenness(v) + w₂·[v is source or sink of a causal chain] − w₃·idf⁻¹(bucket(v))`,
  i.e. reward chain participation, penalise generic hub concepts ("problem", "failure").
- Keep local maxima within 1 hop, then take the top `L = min(24, ⌈0.4·|V|⌉)`.

Over-generating (40%, not 10%) is deliberate: a landmark set that shifts under noise is the single
biggest robustness risk, and every landmark lost costs only its own incident fingerprints.

**2. Relational Fingerprint.** Wang's hash is `(f1, f2, Δt)` — two anchors plus the relation between
them. The direct analogue is **two landmarks plus the typed path between them**:

```
FP = H( desc_ch(A) , desc_ch(B) , pathsig(A→B) , distbucket(A,B) , polarity(A→B) )
```

where `desc_ch` is the channel-specific landmark descriptor and `pathsig` is the ordered sequence of
edge types (with per-step direction) along the shortest typed path, truncated at length 3.

**3. Two channels, one generator.** Only `desc_ch` differs:

| | `desc_sem(v)` | `desc_str(v)` |
|---|---|---|
| contents | coarse semantic bucket id (12 bits) + role class (3 bits) | role class (3 bits) only |
| entropy per pair hash | ~30 bits | ~14–15 bits |
| index | exact hash → posting list (Shazam) | idf-weighted inverted index (Video Google) |
| supports H (domain substitution) | no | yes |

This is the load-bearing decision. A single blended hash that mixes lexical and structural bits cannot
separate "same words, different structure" from "different words, same structure", because both cases
produce partial hash agreement and the score collapses to one number. Two channels give two numbers, and
the hard negative is a **sign test on their difference**, not a threshold on a blend.

## Why paths, not Weisfeiler-Lehman

The obvious literature answer is WL subtree hashing (Shervashidze et al. 2011): `O(hm)` per graph, cheap,
well-supported. **I recommend against it as the fingerprint primitive**, on a robustness argument that I
think dominates its efficiency advantage.

WL label assignment is **non-monotone under insertion**. At iteration `h`, a node's label is a function of
its *exact* `h`-hop neighbourhood multiset. Inserting one irrelevant branch (invariance D) or one
extraction artefact (invariance I) *changes* the labels of every node within `h` hops — those features are
not diluted, they are destroyed. For a 50-node graph at `h=2`, one spurious node can invalidate 5–15 node
labels.

Path shingles are **monotone**: inserting a node *adds* new shingles but leaves every path that does not
traverse it bit-identical. Recall is preserved exactly; only precision degrades, and degrades smoothly.
For a retrieval stage whose entire job is candidate recall under noise, monotone degradation beats a
tighter kernel. WL still earns a place as a *landmark salience* signal and as a baseline in the toy
experiment — just not as the hashed key.

## Rare-triple tail index

Wang notes that combinatorial hashing **squares peak survival**: a pair survives with ≈`p²`. He escapes
this by raising fan-out, since `p·[1−(1−p)^F] ≈ p` for `F ≳ 10`. Resonance can afford the same escape —
a 50-node graph with average degree ~2.5 has roughly 8–12 landmarks within causal distance 3, so `F≈10` is
attainable. But raising *entropy* by moving to triples costs `p³`, and that cannot be bought back the same
way. So triples are used **only in the rare tail**: generate ~`6L` triple candidates, index only the ~5%
whose structural configuration is rarest corpus-wide. Low recall by construction, high precision, and it
is the only mechanism here that can find a cross-domain analogue outside its own shard.

## Consistency test — the analogue of "many hashes agree on one Δt"

Shazam's invariant is a **global scalar translation**: every true hash satisfies `t_db − t_query = const`,
so a 1-D histogram suffices. Graphs have no such scalar, and this is where naive ports usually break.

The correct analogue is **mutual consistency of the induced partial node correspondence**. Every matched
fingerprint asserts two correspondences, `q_a↦c_a` and `q_b↦c_b`. For a true structural match these must
be *mutually injective and distance-consistent*. Concretely:

1. Each matched fingerprint casts votes into a `(q_i, c_j)` correspondence histogram.
2. Keep pairs with ≥2 independent supporting fingerprints.
3. Greedily select a maximum-weight **injective** subset (no `q_i` used twice, no `c_j` used twice),
   rejecting pairs whose implied graph distances disagree by more than one bucket.
4. Score = idf-weighted sum over the surviving consistent set.

Exact maximisation is the max-clique-on-an-association-graph problem and is NP-hard; the greedy pass is
`O(#matches·log #matches)` and is entirely adequate for ranking. This is structurally the same move
Philbin et al. (2007) make with RANSAC spatial verification after bag-of-visual-words retrieval.

There *is* a literal scalar analogue worth keeping as a cheap pre-filter: assign each node a **causal
depth** (longest causal path from a source); for a true chain match, `depth_c − depth_q` is constant, so a
depth-offset histogram is an exact Shazam replay at `O(1)` per match. It is brittle to granularity
(invariance F changes depths), so it is a pre-filter, not the decision.

# Why It Fits Resonance

- **Cheap retrieval, expensive verification** is the brief's pipeline, and this is precisely the MAC/FAC
  split (Forbus, Gentner & Law 1995). Resonance's constraint that the core comparator be non-LLM and
  deterministic is satisfied: everything here is integer hashing, sorting, and counting.
- **It deliberately breaks with MAC/FAC on one point, and that break is the contribution.** MAC/FAC's
  cheap stage is a *content vector* — a flat frequency vector over predicates whose dot product estimates
  structural match. It is explicitly non-structural, and Gentner, Rattermann & Forbus (1993) showed
  empirically that human retrieval built this way is dominated by surface similarity: surface-similar
  remindings far outnumbered structurally similar ones. **A faithful port of MAC's content vector would
  reproduce the surface bias and fail invariance H by construction.** Resonance wants retrieval that is
  *better than human* at cross-domain reminding, which is why the structural channel must exist as a
  separate, lexicon-free index rather than as extra dimensions in one vector.
- **Explainability** falls out for free: the consistency test already computes which query nodes map to
  which candidate nodes, so "which branches correspond and why" is a by-product of retrieval, not a
  separate feature.
- **40–50h budget**: channel one is a dict of posting lists; channel two adds idf weights and a stop-motif
  cut. No training, no new model.

# Required Thought DNA

Only fields the algorithm actually consumes. **Hashed** fields must be discrete and stable; **continuous**
fields must stay out of the key.

**Per node**

| Field | Type | Hashed? | Used for |
|---|---|---|---|
| `id` | local stable id | no | correspondence bookkeeping |
| `semantic_bucket` | int, ~4096 clusters over a multilingual sentence embedding | **yes** (12 bits) | semantic channel |
| `role_class` | enum{entity, process, state, quantity, agent, outcome, condition} | **yes** (3 bits) | both channels |
| `polarity` | −1 / 0 / +1 | **yes** (part of pair polarity) | both |
| `surface_label` | string | **no** | explanation only |
| `embedding` | float vector | **no** | derives `semantic_bucket` offline |
| `extraction_confidence` | float | **no** | vote weighting, pruning |

**Per edge**

| Field | Type | Hashed? | Used for |
|---|---|---|---|
| `relation_type` | **closed vocabulary**: causes, increases, decreases, enables, prevents, requires, part_of, is_a, precedes, contradicts | **yes** | primary structural entropy |
| `direction` | bool | **yes** | the hard negative depends on it |
| `sign` | −1/+1 | **yes** | prevents/causes must not collide |
| `edge_confidence` | float | **no** | vote weighting |

**Not required by this mission** — do not build for retrieval's sake: global graph embeddings, timestamps,
ontology URIs, reified relations, hyperedges, per-node vectors *in the index*.

The closed relation vocabulary is non-negotiable. It is the structural channel's only entropy source; an
open-ended relation string would be a lexical field in disguise and would silently reintroduce the surface
bias the channel exists to avoid.

# Required Graph Representation

**Directed labelled multigraph with typed, signed edges.** Not a tree: causal convergence (several causes,
one outcome) is central to the target examples and trees cannot express it. Multigraph because one node
pair legitimately carries two relations (`A causes B` *and* `A precedes B`), and collapsing them loses the
distinction the structural channel is built on.

**Hypergraph/reification is not needed for retrieval.** Higher-order structure — Gentner's causal bindings
between relations, which drive analogical soundness — is captured *implicitly* by path shingles of length
2–3: the shingle `A −causes→ B −causes→ C` already is a second-order pattern. Reification may still be
required by the verification stage (R0-C); that decision should not be forced here.

# Invariances

| Transformation | Supported | Partially | Not Supported | Mechanism |
|---|---|---|---|---|
| A paraphrase | ✅ | | | semantic bucket is embedding-derived, not lexical |
| B vocabulary substitution | ✅ | | | same; fails only at bucket boundaries |
| C node ordering | ✅ | | | fingerprints are a *set*; pair canonicalised by (role, bucket) sort |
| D irrelevant branch insertion | | ⚠️ | | path shingles are monotone under insertion; idf + `min(|Q|,|C|)` normalisation limits dilution |
| E partial observation | | ⚠️ | | **containment** normalisation, not symmetric Jaccard, so a fragment can retrieve the whole |
| F different granularity | | ⚠️ | | derived transitive `causal_reaches` edges (≤3 hops collapsed) + coarse distance buckets; breaks past ~3:1 ratio |
| G different graph sizes | | ⚠️ | | per-query top-k fingerprint budget + containment scoring stops large thoughts dominating |
| H domain substitution | | ⚠️ | | structural channel is lexicon-free **in principle**; entropy budget limits it to bounded shards + rare-triple tail |
| I extraction mistakes | | ⚠️ | | pair survival `p²` offset by `F≈10` fan-out (Wang); **edge-type errors remain fatal** |

Two honest weak spots: **F** is the weakest invariance here and properly belongs to R0-D's multiscale
question; **I** is asymmetric — node errors are survivable, a mislabelled `causes`→`correlates` destroys
every fingerprint through that edge.

# Retrieval vs Verification

**FAST RETRIEVAL**, unambiguously. This layer must never decide that two thoughts resonate.

Index (per channel): `hash → [(thought_id, anchor_landmark_id, idf_weight)]`, sorted by hash, mmap-able.
Wang's 64-bit struct generalises directly: 32-bit key, 32-bit payload (24-bit thought id + 8-bit landmark
id).

**Output contract to the verifier — this is the important interface claim.** Retrieval must return

```
(thought_id, score, seed_correspondences: [(q_node, c_node, support)])
```

not merely ranked IDs. Shazam's histogram already tells you *where in the song* the match sits; the
correspondence-consistency test already computes seed node pairs, and discarding them forces R0-C's
verifier to re-derive an alignment from scratch. Seeded alignment is dramatically cheaper than cold
alignment, so this hand-off should be treated as a hard requirement on the retrieval/verification boundary.

# Computational Cost

**Fingerprint generation, 50-node thought.** Landmark scoring is one betweenness pass, `O(|V||E|)` ≈ 6k ops;
bounded BFS to depth 3 from 20 landmarks ≈ `20 × 25` node visits. Sub-millisecond in C, ~5 ms in Python.
Emitted: ~200 semantic + ~200 structural (pruned to ~80 indexed) + ~6 rare triples ≈ **~290 stored
fingerprints**, i.e. 5–7× node count — the same design ratio as Wang's `density × F`.

**Corpus of 10⁶ thoughts.** ~3×10⁸ postings × 8 bytes ≈ **2.4 GB**, RAM-resident on one machine.

**Query cost — the decisive number.**

| | key entropy | keys | postings | mean postings/key | postings touched per query |
|---|---|---|---|---|---|
| Shazam (10⁶ tracks) | 30 bits | ~10⁹ | ~2×10⁹ | ~2 | ~4×10³ |
| Resonance semantic ch. | ~30 bits | ~10⁹ | 2×10⁸ | <1 | ~10³ |
| Resonance structural ch. | ~15 bits | 3.3×10⁴ | 8×10⁷ | ~2,400 | **~2×10⁵ (uniform) / ~10⁷ (Zipfian tail)** |

The semantic channel is Shazam-grade. The structural channel is **two to four orders of magnitude worse**,
and that gap is the entire content of this report. It is brought back to feasibility only by: (i) hard
stop-motif pruning (drop keys with `df > 0.1%` of corpus), (ii) a fixed query budget of the top-64
fingerprints by idf, and (iii) capping posting lists by priority sampling. With all three, worst-case work
per query is bounded at ~6.4×10⁵ postings — tens of ms in a compiled index.

**Top-20 verification** is R0-C's cost, but note the seeds above reduce it materially.

# Existing Implementations

| Library | Use | Maturity / risk |
|---|---|---|
| **networkx** | graph model, BFS, betweenness, path enumeration | mature, pure-Python, slow at scale but fine for MVP |
| **datasketch** (ekzhu) | MinHash / MinHashLSH / Weighted MinHash / LSH Ensemble; Redis & Cassandra backends | mature, widely deployed. **Fallback only** — see below |
| **GraKeL** (JMLR 2020, 16 kernels, sklearn API) | WL / neighbourhood-hash / graphlet **baselines** for the toy experiment | research library, peer-reviewed; slower release cadence — do not put on the production path |
| plain `dict` + `numpy` + `pickle` | the actual index for MVP | zero dependency risk; sufficient to ~10⁵ thoughts |
| **PGD** / **ORCA** | graphlet-orbit baselines if GDV is tested | C++, UNIX-only, build friction; optional |
| **faiss** | only if a dense fallback is ever needed | mature, but dense retrieval loses correspondences — see *What NOT To Build* |

On **MinHash-LSH**: it is a genuinely reasonable alternative index, and its Jaccard semantics match the
graceful-degradation property I argue for. I do not recommend it as *primary* for one reason: it returns a
similarity estimate without telling you *which* shingles matched, which destroys the correspondence vote
and therefore both the consistency test and the seed hand-off. Keep it as the escape hatch if posting
lists prove unmanageable.

# Minimal Pseudocode

```python
REL = {"causes":0,"increases":1,"decreases":2,"enables":3,"prevents":4,
       "requires":5,"part_of":6,"is_a":7,"precedes":8,"contradicts":9}   # closed, 4 bits
ROLE = {"entity":0,"process":1,"state":2,"quantity":3,
        "agent":4,"outcome":5,"condition":6}                              # 3 bits

def landmarks(G, frac=0.4, cap=24):
    sal = {v: (2.0*causal_betweenness(G,v)
               + 1.0*is_chain_endpoint(G,v)
               - 0.5*generic_penalty(G.nodes[v]["semantic_bucket"]))
           for v in G if has_typed_edge(G,v)}
    peaks = [v for v in sal if sal[v] >= max(sal[u] for u in nbrs1(G,v)+[v])]
    return sorted(peaks, key=sal.get, reverse=True)[:min(cap, ceil(frac*len(G)))]

def pathsig(G, a, b, maxlen=3):
    p = shortest_typed_path(G, a, b, maxlen)          # None if farther than maxlen
    if p is None: return None
    sig = 0
    for (u, v, data) in p:                            # ≤3 steps
        step = (REL[data["relation_type"]] << 1) | (1 if data["forward"] else 0)
        sig = (sig << 5) | step
    return sig                                        # ≤15 bits

def fingerprints(G, channel, F=10):
    out = []
    L = landmarks(G)
    for a in L:
        targets = [b for b in bfs_within(G, a, 3) if b in L and b != a][:F]  # fan-out cap
        for b in targets:
            sig = pathsig(G, a, b)
            if sig is None: continue
            da, db = desc(G, a, channel), desc(G, b, channel)   # 15 bits / 3 bits
            key = h32(da, db, sig, dbucket(G,a,b), pol(G,a,b))
            out.append((key, a))                       # anchor kept as payload
    return out

def build_index(corpus):
    idx = defaultdict(list); df = Counter()
    for tid, G in corpus:
        for ch in ("sem", "str"):
            fps = fingerprints(G, ch)
            if ch == "str":
                fps = keep_top_idf(fps, frac=0.4)      # structural pruning
            for key, anchor in fps:
                idx[(ch, key)].append((tid, anchor)); df[(ch, key)] += 1
    for k in [k for k in idx if df[k] > 0.001*len(corpus)]:
        del idx[k]                                     # stop-motif cut
    return idx, {k: log(len(corpus)/df[k]) for k in idx}

def query(G, idx, idfw, K=20, budget=64):
    votes = defaultdict(lambda: defaultdict(float))    # tid -> (q,c) -> weight
    for ch in ("sem", "str"):
        fps = fingerprints(G, ch)
        fps = sorted(fps, key=lambda kv: -idfw.get((ch,kv[0]), 0))[:budget]
        for key, q_anchor in fps:
            for (tid, c_anchor) in idx.get((ch, key), ()):
                votes[tid][(q_anchor, c_anchor)] += idfw[(ch, key)]
    scored = []
    for tid, pairs in votes.items():
        cons = greedy_injective_consistent(pairs, G, tid)   # the Δt analogue
        s = sum(w for (_, w) in cons) / sqrt(min(len(G), size(tid)))
        scored.append((tid, s, [(q, c, w) for ((q, c), w) in cons]))
    return sorted(scored, key=lambda r: -r[1])[:K]     # (tid, score, SEED CORRESPONDENCES)
```

**Concrete fingerprint record** (the mission's required artifact):

```json
{
  "channel": "str",
  "key": 24917,
  "decoded": {
    "role_a": "process", "role_b": "outcome",
    "pathsig": ["causes:fwd", "causes:fwd"],
    "dist_bucket": 2, "polarity": "+"
  },
  "thought_id": 811403,
  "anchor_landmark": 7,
  "idf": 4.81
}
```

The battery example emits `(process, outcome, [causes,causes], 2, +)`; so does the organisation example,
with a *disjoint* `sem` channel. That divergence — high `str` agreement, near-zero `sem` agreement — is the
signature of cross-domain analogy, and it is only observable because the channels were never blended.

# Toy Experiment

**Implementable in ≤2 hours; designed to falsify me.**

*Inputs.* 12 hand-written relational templates (6–10 nodes: causal chains, converging causes, feedback
loops). Each template realised four ways: **(1)** domain X; **(2)** paraphrase of X; **(3)** domain Y with
*disjoint* vocabulary, structure preserved; **(4)** domain X vocabulary with edges rewired/reversed — the
hard negative. That is 48 graphs. Add 200 generic filler graphs, then synthetically replicate fillers with
random relabelling to 10³ / 10⁴ / 10⁵ to expose posting-list skew.

*Procedure.* Index everything; query with (1).

*Metrics and falsification thresholds.*

| | Metric | My prediction | Falsifies me if |
|---|---|---|---|
| M1 | Recall@20 of (3), **structural channel only** | 0.5–0.7 | **< 0.5** |
| M2 | Recall@20 of (2), semantic channel | > 0.9 | < 0.8 |
| M3 | AUC separating (3) from (4) using `str − sem` | ~0.85 | **< 0.75** |
| M4 | postings touched/query as corpus 10³→10⁵ | sub-linear after pruning | **linear** |

If M1 or M3 fails, the structural channel is **not a retrieval index** and the correct architecture demotes
structure to verification-only, with retrieval running semantic-only inside topic shards. That is a real
NO-GO path and I would report it as such. If M4 fails, the entropy argument bites harder than my mitigations
and sharding becomes mandatory rather than optional.

# Failure Modes

1. **Motif collapse (most likely).** If ~80% of real thoughts reduce to `X causes Y causes Z`, the
   structural key is near-constant, every posting list is the corpus, and the channel dies. This is the
   failure M1/M4 are built to detect.
2. **Bucket-boundary cliff.** "car battery degradation" and "cell capacity fade" are paraphrases that may
   quantise to different clusters. Vector quantisation is a hard cliff, and no amount of fan-out fixes a
   systematic boundary error. Mitigation: assign each node its top-2 buckets and emit both fingerprints —
   at 2× storage.
3. **Hub explosion.** Generic nodes ("failure", "problem", "cost") become landmarks in a large fraction of
   thoughts and their fingerprints swamp every vote. The `generic_penalty` term and the stop-motif cut are
   both aimed here; neither is proven adequate.
4. **Direction/polarity adversary.** "stress causes insomnia" vs "insomnia causes stress" share every node
   and every bucket. Only the direction bit separates them. Any extraction error on direction produces a
   confident false positive — the worst failure class for user trust.
5. **`prevents` vs `causes`.** Identical topology, inverted meaning. If sign is dropped from the key, the
   structural channel will confidently rank an intervention as analogous to the disease.
6. **Granularity divergence.** The same thought extracted at two depths (`A→B` vs `A→X→Y→B`) lands in
   different distance buckets and shares few shingles. Transitive `causal_reaches` edges patch the ≤3-hop
   case and nothing beyond.
7. **Fragment scoring.** A 10-node fragment emits ~40 fingerprints against a 100-node thought's ~600. With
   symmetric Jaccard the fragment never retrieves its parent; containment normalisation is mandatory, not
   an optimisation.
8. **Survival compounding.** Wang's `p²` applies here too, but node survival under paraphrase *plus*
   re-extraction is plausibly ~0.7 rather than a codec's ~0.9 — so pair survival ~0.49, triple survival
   ~0.34. The rare-triple tier is the most fragile component in the design and should be treated as
   experimental.

# What NOT To Build

- **A GNN or learned graph embedding for retrieval.** Violates the no-new-model constraint, and a dense
  vector returns a score with no correspondence — killing both the consistency vote and explainability.
- **WL subtree hashes as the fingerprint key.** Non-monotone under insertion (see above). Keep WL as a
  baseline, not as the primitive.
- **Exact graphlet/orbit vectors (GDV) as the retrieval key.** Global, correspondence-free, expensive, and
  it answers "how similar" when retrieval needs "which parts correspond".
- **A single blended lexical+structural hash.** Cheapest-looking option, and it makes the project's central
  hard negative formally undecidable.
- **A universal ontology for semantic buckets.** Retrieval needs *some* stable coarse clustering, nothing
  more. Scoping the ontology question is R0-E's job and should not be pre-empted here.
- **An LLM anywhere in the comparison or index path.** Explicitly excluded by the brief; also destroys
  determinism and reproducibility of the benchmark.
- **MinHash-LSH as the primary index** — see *Existing Implementations*. Escape hatch, not default.

# Architecture Consequences

1. Thought DNA must carry a **closed, small relation vocabulary** with explicit direction and sign. This is
   the single highest-leverage constraint in the whole design.
2. Retrieval requires **two independently scored channels**; the API must expose both scores, never a blend.
3. The retrieval contract returns **seed node correspondences**, not just candidate IDs.
4. Node semantic buckets are a **derived, versioned artifact**; re-clustering invalidates the semantic index
   and must be a versioned migration, not a silent rebuild.
5. `role_class` is a required extraction output and must be predicted even when the surface label is
   ambiguous.
6. Graphs are **directed labelled multigraphs**; reification is deferred to the verification decision.
7. Index maintenance needs corpus-wide document frequencies — so **idf is global mutable state** and
   incremental insertion must handle drifting stop-motif thresholds.
8. Cross-domain retrieval should be **budgeted and sharded** from day one; do not promise flat 10⁶-scale
   cross-domain lookup on the structural channel.
9. Scoring must use **containment**, not symmetric Jaccard, or partial thoughts are unretrievable.
10. The benchmark (R0-G) must include the "same words / different structure" pair as a first-class case;
    a suite without it cannot distinguish this architecture from a bag-of-words baseline.

# Mission Questions — Direct Answers

1. **Robust Cognitive Landmark** — a node in a relational role, selected by causal-chain participation and
   local salience maxima, over-generated to 40% of nodes.
2. **Relational Fingerprint** — `(desc(A), desc(B), pathsig(A→B), distbucket, polarity)` packed to 32 bits,
   the direct analogue of Wang's `(f1,f2,Δt)`.
3. **Hashed**: semantic bucket, role class, relation types + direction + sign, distance bucket.
   **Continuous** (never in the key): embeddings, extraction/edge confidence, idf weights.
4. **~290 stored fingerprints for a 50-node thought** (~200 semantic, ~80 pruned structural, ~6 rare
   triples) — 5–7× node count, mirroring Wang's `density × F`.
5. **Rare selection** — global idf ranking, top-64 query budget, tail-only triple indexing.
6. **Generic-motif control** — hard `df > 0.1%` stop-motif cut, posting-list priority sampling, and a
   generic-concept penalty in landmark scoring.
7. **Survivable transformations** — A, B, C fully; D, E, G, I with graceful degradation; F and H only
   partially, with H bounded by the entropy budget.
8. **Index for 10⁶ thoughts** — sorted 64-bit posting arrays (32-bit key / 24-bit thought id / 8-bit
   landmark), ~2.4 GB, mmap-able; MinHash-LSH as fallback.
9. **Consistency test** — mutual injective consistency of induced node correspondences (greedy
   max-weight), with a causal-depth-offset histogram as the literal-but-brittle scalar analogue.
10. **Thought DNA requirements** — see the field table; the closed relation vocabulary and the direction/
    sign bits are the non-negotiable parts.

# Sources

1. **Wang, A. L.-C. (2003). "An Industrial-Strength Audio Search Algorithm." ISMIR 2003.** The primary
   source for the entire analogy, and the source of this report's central argument. Wang performs the
   entropy accounting explicitly — a 1024-bin frequency axis gives "at most 10 bits" per peak, pairing
   yields 30 bits and "about a million times greater" specificity — and states the `p²` survival penalty
   and the `F=10` fan-out escape. Everything I claim about why the structural channel is *not* Shazam-grade
   is a direct application of his own accounting.
   https://www.ee.columbia.edu/~dpwe/papers/Wang03-shazam.pdf
2. **Forbus, K., Gentner, D., & Law, K. (1995). "MAC/FAC: A Model of Similarity-Based Retrieval."
   Cognitive Science 19(2), 141–205.** The cheap-retrieval/expensive-verification split Resonance is
   built on. Critically, its MAC stage is a *non-structural* content vector over predicate frequencies —
   the design I argue Resonance must deliberately not copy.
   https://www.qrg.northwestern.edu/papers/Files/macfac91(searchable).pdf
3. **Gentner, D., Rattermann, M. J., & Forbus, K. (1993). "The roles of similarity in transfer: separating
   retrievability from inferential soundness." Cognitive Psychology 25(4), 524–575.** Empirical evidence
   that surface-similar remindings far outnumber structural ones in human retrieval. This is the
   experimental basis for claiming a content-vector-style retrieval stage will fail invariance H.
   https://pubmed.ncbi.nlm.nih.gov/8243045/
4. **Gentner, D. (1983). "Structure-Mapping: A Theoretical Framework for Analogy." Cognitive Science 7(2),
   155–170.** Establishes that analogy is carried by relational and higher-order structure rather than
   object attributes — the reason a lexicon-free channel must exist at all.
5. **Shervashidze, N., Schweitzer, P., van Leeuwen, E. J., Mehlhorn, K., & Borgwardt, K. (2011).
   "Weisfeiler-Lehman Graph Kernels." JMLR 12, 2539–2561.** The strongest competing primitive, `O(hm)` per
   graph. Cited here for the position I argue *against*: WL's exact `h`-hop label dependence is
   non-monotone under insertion, which matters more than its speed for a noisy retrieval stage.
   https://jmlr.org/papers/v12/shervashidze11a.html
6. **Sivic, J., & Zisserman, A. (2003). "Video Google: A Text Retrieval Approach to Object Matching in
   Videos." ICCV 2003.** The correct model for a *low-entropy* key: vector-quantised visual words with
   tf-idf weighting, an inverted file, and a stop list. This is the template for the structural channel,
   and the reason I do not model it on Shazam.
   https://www.robots.ox.ac.uk/~vgg/publications/2003/Sivic03/sivic03.pdf
7. **Philbin, J., Chum, O., Isard, M., Sivic, J., & Zisserman, A. (2007). "Object Retrieval with Large
   Vocabularies and Fast Spatial Matching." CVPR 2007.** Establishes the retrieve-then-geometrically-verify
   pattern at scale. The correspondence-consistency test is the graph transposition of its spatial
   verification step.
8. **Hido, S., & Kashima, H. (2009). "A Linear-Time Graph Kernel." ICDM 2009.** Neighbourhood hashing via
   bitwise XOR/rotation of binary node labels — the cheapest known way to get a node descriptor, and the
   implementation route for `desc_str` if betweenness proves too slow.
   https://www.semanticscholar.org/paper/619cdd400f94702638fbb64eca63f36289b78d81
9. **Broder, A. (1997). "On the Resemblance and Containment of Documents." SEQUENCES '97.** Source of both
   MinHash and, more importantly here, the **containment** measure that invariances E and G require.
10. **Siglidis, G. et al. (2020). "GraKeL: A Graph Kernel Library in Python." JMLR 21.** 16 kernels behind a
    scikit-learn API — the fastest way to run WL / neighbourhood-hash / graphlet baselines in the toy
    experiment without reimplementing papers. https://www.jmlr.org/papers/v21/18-370.html
11. **`datasketch` (ekzhu).** Production-grade MinHash, Weighted MinHash, LSH Forest and LSH Ensemble with
    Redis/Cassandra backends — the concrete fallback index if posting lists prove unmanageable.
    https://github.com/ekzhu/datasketch
12. **Ribeiro, P. et al. (2021). "A Survey on Subgraph Counting: Concepts, Algorithms, and Applications to
    Network Motifs and Graphlets." ACM Computing Surveys 54(2).** Authoritative cost picture for graphlet
    and motif counting; the basis for rejecting exact orbit vectors as a retrieval key.
    https://dl.acm.org/doi/abs/10.1145/3433652

---

## Provenance and independence

- **Blind constraint (R0-B):** preserved. I did not open PR #24, its diff, or any R0-B1 artifact. B1's
  submission is not merged into `main`, so it was absent from my working tree throughout. To establish
  canonical mission state under `work/STATE_MACHINE.md` I read only the `CLAIM`/`SUBMIT` coordination
  headers on issue #4 — no B1 result content.
- **Additional voluntary isolation (disclosed, not required):** I also did not read the already-merged
  submissions for R0-A, R0-C2, or R0-D, although the contract permits it, so that any convergence between
  this report and adjacent missions is evidence rather than an artifact of anchoring. Reconciling this
  report's granularity claims with R0-D, and its retrieval/verification interface with R0-C, is left to the
  #13 synthesis gate.
- **Method:** repository reading, web search, and retrieval of primary PDFs. The Wang (2003) figures quoted
  above were extracted from the paper itself, not from secondary summaries.
- **Tools:** Claude Code CLI with web search/fetch and local shell. No code was executed against a Thought
  Graph corpus — none exists yet — so every quantitative claim here is an analytic estimate, explicitly
  labelled as such, and the toy experiment is the proposed way to check it.
- **Not performed:** no benchmark run, no corpus measurement, no implementation. This is a design decision
  document, and its central empirical claim (structural-channel entropy) is unverified by construction.
