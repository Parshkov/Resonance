---
mission: R0-B
run: B3 (independent repeat, REPEAT_CLAIM; blind group R0-B)
contributor: DenisVParshin
agent_or_model: Claude Fable 5 (claude-fable-5), Claude Code CLI
date: 2026-08-31
mission_modified: false
web_research_used: true
independence_disclosure: >
  Blind constraint honored with two disclosed leaks. (1) Neither R0-B1 (PR
  #24, unmerged, unread) nor R0-B2 (merged; file deliberately left unopened)
  was read; however, a repository-wide grep during an earlier security review
  surfaced ONE table row from R0-B2 comparing Shazam bit budgets ("30 bits /
  ~10^9 …"). (2) The same grep surfaced ~9 fragment lines from the merged
  R0-D submission mentioning path-length buckets {1,2,3+}, IDF-weighted
  inverted postings, a structural/semantic two-channel token split, and
  per-thought token caps. This report also uses length-bucketed path tokens,
  a two-channel split, IDF weighting, and token caps — convergence on THOSE
  SPECIFIC elements must not be counted as independent. The entropy-budget
  framing was developed independently in this agent's R0-H2 run from the
  primary Shazam paper, but the B2 grep row shows B2 reasoned about bit
  budgets too — treat that theme as potentially convergent-by-leak.
  Same-agent note: one of eight sequential runs by one agent in one session;
  this run is heavily anchored by my own R0-H2.
---

# Decision

Direct answer to the decision question: **No as the primary retrieval layer;
qualified yes as a secondary recall channel.** A Shazam-like sparse
fingerprint over typed Thought Graphs cannot carry primary retrieval at 1M
scale, because the available token entropy (~10–14 heavily skewed bits) is
insufficient, extraction noise exceeds what token-exact hashing absorbs, and
the mechanism that makes Shazam precise — the global 1-D offset-consistency
histogram — has no cheap graph analogue (its analogue is the NP-hard
alignment deferred to verification). The best available design under the
mission's own constraints is specified below anyway: **typed anchor-path
constellation tokens** in two channels (delexicalized structural + coarse
semantic), IDF-filtered, served from an inverted index with anchor-consistent
voting. It should be built *only if* it first passes a self-retrieval gate
(paraphrase → re-extraction → R@10 ≥ 0.9 against distractors), and deployed
only next to an embedding-led primary channel, never instead of one.

# Confidence

HIGH on the negative half (it follows from the primary Shazam source,
arithmetic on the token space, and the measured extraction-consistency
ceiling). MEDIUM on the positive half — the proposed record is the reasonable
optimum of the design space, but no evidence yet shows it adds recall over
embeddings of delexicalized skeleton renderings, which achieve a similar goal
with mature infrastructure. Main uncertainty: the actual token-collision
statistics on real extracted graphs — measurable only via R0-G.

# Answers to the mission's Resolve questions

1. **A robust Cognitive Landmark** is not a node (labels are unstable, types
   are 10-way at best — README's ten; the sibling F3 proposal narrows to
   six, which shrinks structural entropy further) but an **anchor node plus its typed relational
   context**: the multiset of outgoing/incoming typed, polarity-signed paths
   of bucketed length. Robustness comes from redundancy (many landmarks per
   thought), not from individual landmark stability — individually, every
   landmark is weak; this is the honest transfer of Shazam's "1–2% of hashes
   suffice" property, and it survives only if the *voting* stage works.
2. **A Relational Fingerprint** is the capped, IDF-weighted set of
   constellation tokens of one Thought Graph (concrete record below).
3. **Discretized:** node types, edge types, polarity, path-length bucket
   {1, 2, 3+}, coarse semantic bucket of endpoint labels (k-means over label
   embeddings, k=256, cluster id only). **Continuous (never hashed):** label
   embeddings themselves, systematicity depth, any scores — those belong to
   verification.
4. **Token count for ~50 nodes:** all nodes are anchors; paths per anchor
   capped at 8; raw ≈ 200–400 tokens; after IDF-based selection cap at
   **128 structural + 64 semantic tokens** per thought.
5. **Rare/high-information selection:** corpus document-frequency; keep the
   lowest-DF tokens per thought up to the cap; drop the global top ~1% DF
   tokens entirely (structural stopwords — exactly the generic
   goal→constraint→mechanism chains).
6. **Generic-motif suppression:** the DF stoplist above + per-token IDF
   weight in scoring + a hard cap on posting-list length visited per query
   (early-exit). Accept openly: this deletes the most common structures from
   retrievability — thoughts whose entire structure is generic are simply
   not retrievable by structure, which is correct behavior.
7. **Survivable transformations:** B (vocabulary substitution) and H (domain
   substitution) — the structural channel is delexicalized, this is its
   raison d'être; C (ordering) trivially; D/G partially via set semantics +
   IDF. **Not survivable:** A/I when paraphrase or re-extraction changes
   decomposition (token-exact hashing breaks — the self-retrieval gate
   exists precisely for this); F beyond the {1,2,3+} bucket (deep
   granularity changes reshape paths).
8. **Index for 1M thoughts:** classic inverted index, token → postings of
   `(thought_id, anchor_node_id)` with IDF in the dictionary. Scale: 1M ×
   192 tokens × ~16 B ≈ 3 GB — single-machine RAM or RocksDB; no ANN
   infrastructure needed. (The *embedding* primary channel uses FAISS/HNSW
   separately.)
9. **The analogue of Shazam's offset-consistency test** — the mission's
   hardest question — is **anchor-consistency voting**: group token matches
   by (query_anchor, candidate_anchor) pairs; greedily commit each query
   anchor to its best candidate anchor (one-to-one); a candidate's score is
   the IDF-weighted mass of committed pairs, and a minimum of m ≥ 3
   committed anchors is required. This is a 0-dimensional, local-consistency
   shadow of Shazam's global 1-D histogram: cheap (O(matched postings)), but
   categorically weaker — it checks that matches concentrate on a coherent
   set of anchor pairs, not that one global alignment explains them. The
   honest conclusion: the full consistency test *is* verification (R0-C),
   and no cheap substitute recovers Shazam's precision. This is the deepest
   point where the analogy fails.
10. **Thought DNA requirements:** closed typed edges with polarity and
    stable type vocabulary (any type drift corrupts every token); core/
    peripheral status from extraction (fingerprint core only); extractor
    version scoping; node labels available for semantic bucketing.

# Required artifact — fingerprint record, query, voting

```json
{
  "thought_id": "t-8842",
  "extractor_version": "dna-0.1/claude-x/prompt-3f2a",
  "channel_s": [
    {"tok": "S|state>causes+>state>causes+>event|len2", "anchor": "n3", "idf": 7.1},
    {"tok": "S|entity>requires+>constraint|len1",        "anchor": "n1", "idf": 4.9}
  ],
  "channel_k": [
    {"tok": "K|c142>causes+>c077|len1", "anchor": "n3", "idf": 9.0}
  ]
}
```

`S|…` tokens are fully delexicalized (types/polarity/length only); `K|…`
tokens replace endpoint labels with coarse cluster ids (c142 = e.g. the
"accumulation/overload" label cluster), trading some domain-invariance for
precision. Query: extract the probe's fingerprint the same way; fetch
postings for its tokens (skipping stoplisted); accumulate
`score[cand] += idf(tok)` grouped by anchor pairs; apply greedy one-to-one
anchor commitment; rank candidates by committed mass; require m ≥ 3; return
top-K to the verifier. Both channels are queried; candidate set is the union
(structural channel supplies cross-domain recall, semantic channel supplies
precision).

# Invariances

| Transformation | Supported | Partially | Not | Mechanism |
|---|---|---|---|---|
| A paraphrase | | X | | survives only when decomposition is stable; the self-retrieval gate measures exactly this |
| B vocabulary substitution | X | | | delexicalized S-channel |
| C node ordering | X | | | set semantics |
| D irrelevant branches | | X | | IDF selection + caps; dilution risk on verbose graphs |
| E partial / missing nodes | | X | | set overlap degrades gracefully, but the m ≥ 3 anchor floor can reject small fragments |
| F granularity | | X | | only the {1,2,3+} length bucket; deeper changes reshape paths |
| G size difference | | X | | per-thought caps equalize, asymmetric dilution remains |
| H domain substitution | X | | | the S-channel's raison d'être |
| I extraction mistakes | | | X | token-exact hashing; the dominant failure mode, hence the gate |

# Retrieval vs Verification

FAST RETRIEVAL — but explicitly as the **secondary** recall channel beside
embedding retrieval (raw text + delexicalized skeleton rendering). If the
benchmark shows the union adds < 5 recall points over embeddings alone on
cross-domain pairs, delete this component without regret; every design
element above is disposable, the verifier is not.

# Computational Cost

Fingerprint build: linear in edges, microseconds. Query: ~192 dictionary
lookups + bounded posting scans; « 10 ms warm at 1M scale. Index: ≈ 3 GB
RAM; rebuild is a linear scan (re-extraction, not indexing, dominates
lifecycle cost). 50×50 comparisons and top-20 verification are out of scope
here (R0-C).

# Existing Implementations

Inverted index: trivial in Python dicts for the MVP; `rocksdb`/`sqlite` for
persistence. MinHash/LSH (`datasketch`, mature) — considered and **not**
recommended v0.1: Jaccard sketching adds approximation loss on top of an
already entropy-poor signal; exact posting intersection is affordable at
this scale. WL refinement (via `grakel`/hand-rolled, mature theory —
Shervashidze et al. 2011) — considered as token generator; rejected for
v0.1 because WL subtree labels over 6 node types collapse to few distinct
values at radius 1–2 yet explode combinatorially with label noise at radius
≥ 2; path tokens are more controllable and more explainable ("these two
thoughts share accumulation→degradation→failure chains" is a legible reason).

# Minimal Pseudocode

```
def tokens(G):                                  # core-status elements only
    for a in G.nodes:
        for p in typed_paths(G, a, max_len=3, cap=8):
            yield ("S|"+sig(p.types, p.polarities, bucket(len(p))), a)
            yield ("K|"+sig(cluster(p.ends), p.polarities, bucket(len(p))), a)

def query(probe, index, m=3, K=50):
    votes = defaultdict(lambda: defaultdict(float))   # cand -> (qa,ca) -> w
    for tok, qa in select_by_idf(tokens(probe), cap=192):
        for (cand, ca) in index.postings(tok):        # stoplist + scan cap
            votes[cand][(qa, ca)] += index.idf(tok)
    scored = {c: greedy_one_to_one_mass(v) for c, v in votes.items()}
    return top(K, {c: s for c, (s, n) in scored.items() if n >= m})
```

# Toy Experiment

≤2h, and it is a **gate, not a demo**: 20 thoughts × 3 paraphrases, second
independent extraction of originals, 100 distractors (R0-H2's design).
Build the index over all; query each paraphrase. Metrics: self-retrieval
R@1/R@10; token-survival rate between the two extractions of the same text;
posting-list length distribution (verifies the Zipf-collapse prediction).
**PASS requires R@10 ≥ 0.9.** Below that, this channel is falsified for
primary use and demoted or deleted; the embedding channel takes over recall
entirely.

# Failure Modes

1. Re-extraction changes one node type inside a path → every token through
   that node changes → silent recall collapse (the gate catches it).
2. Zipf token distribution → a few tokens own megaposting lists → scan caps
   turn into recall loss exactly on generic-structure thoughts.
3. Cluster drift in channel K (re-clustering relabels c-ids) → index-wide
   invalidation; cluster model must be versioned with the extractor.
4. Anchor voting rewards hub nodes (high-degree anchors accumulate mass) →
   normalize per-anchor contribution.
5. Adversarial/pathological verbosity floods the cap with boilerplate
   tokens, evicting informative ones → select by IDF, not by order.
6. The channel quietly free-rides on channel K's semantics and claims
   structural success — benchmark must ablate channels separately.

# What NOT To Build

Landmark-pair hashing transplanted literally (two node labels + graph
distance — label instability squares, per Wang's own p² survival argument);
MinHash/LSH over an entropy-poor token set; WL labels at radius ≥ 2 over
noisy small graphs; learned hash functions (no-training rule); any design
whose recall claim has not passed the self-retrieval gate.

# Architecture Consequences

- Fingerprints consume only `core`-status elements (R0-F) and are scoped to
  extractor+cluster version.
- The DF stoplist and IDF tables are corpus artifacts — version and ship
  them with the index.
- Retrieval architecture = embeddings primary (raw + skeleton), constellation
  tokens secondary, union fed to verifier; ablation of the secondary channel
  is a standing benchmark item.
- The anchor-consistency vote is the *only* consistency check at retrieval
  time; do not let anyone claim Shazam-grade precision for it.
- Self-retrieval R@10 ≥ 0.9 is the activation gate for this entire
  component.

# Sources

1. Wang — *An Industrial-Strength Audio Search Algorithm*, ISMIR 2003 (read
   in full in this session). Hash construction, 30-bit entropy, the offset
   histogram, the p² survival argument, the live-recording failure — the
   constraints this design is measured against.
2. Forbus, Gentner, Law — *MAC/FAC*, Cognitive Science 1995. The precedent:
   the cheap analogy-retrieval stage was made non-structural on purpose;
   this report's "secondary channel only" verdict is the same conclusion
   under modern infrastructure.
3. Shervashidze et al. — *Weisfeiler-Lehman Graph Kernels*, JMLR 12, 2011.
   The WL token alternative evaluated and rejected for v0.1.
4. Broder — *On the Resemblance and Containment of Documents*, 1997 (MinHash;
   with `datasketch` as the practical implementation). The sketching
   alternative evaluated and rejected at this scale.
5. Banarescu et al. — AMR + IAA studies (expert same-sentence Smatch ≈
   0.83–0.89). The noise floor that token-exact hashing must survive and
   demonstrably cannot, absent an agreement-core front end.
6. Gick, Holyoak — *Analogical Problem Solving*, 1980. Human retrieval is
   surface-first; a structure-first index swims against the only existence
   proof we have of analogy retrieval working at all.
