# Candidate Retrieval with a Gated Structural Shadow Channel

Status: proposed

Date: 2026-08-31

## Context

Resonance needs to reduce a large thought corpus to roughly 20 candidates before
structural verification. R0-B1 and R0-B2 independently support sparse local
fingerprints, inverted postings, IDF/common-motif suppression, coherent
correspondence voting, and returning seed node pairs. They disagree on how
credible a lexicon-free structural index is at one million thoughts. B2
estimates about 15 key bits and severe Zipfian posting lists, while the semantic
channel has about 30 bits. R0-H then demonstrates a concrete generic-causal
motif where an intended analogy ties four spurious analogues at path-bag
Jaccard 1.0. That toy omits B1/B2's landmark descriptors, distance buckets, and
correspondence-consensus vote, so it invalidates naive path bags and establishes
a serious entropy risk; it does not by itself falsify the complete constellation
design.

The same evidence shows why one blended lexical/structural hash is invalid: it
cannot distinguish the project's paired hard cases. Knowledge DNA adds useful
same-domain and directional complementary recall, but R0-E and R0-H agree that
it is not analogical identity.

## Decision

Use three independent candidate channels and expose their scores separately:

1. **content channel (default):** BM25 and/or an existing versioned semantic
   representation over node labels/source text for paraphrase and same-domain
   recall;
2. **knowledge channel (default when annotated):** IDF-weighted posting lists
   over specific `knowledge.about` IDs and directional
   `query.requires -> candidate.about` joins; and
3. **structural channel (shadow-only initially):** sparse role/relation path or
   landmark-pair fingerprints with IDF, a hard document-frequency cutoff, a
   fixed query budget, coherent injective endpoint voting, and no semantic bits
   blended into the structural score.

The candidate service returns the deduplicated union, channel ranks/scores, and
optional seed correspondences. The structural channel does not affect user
results or production recall claims until it passes the promotion gates below.
The default v0.1 therefore makes no claim of global cross-domain analogical
recall. It can verify a cross-domain pair supplied by content overlap, a user,
an experiment, or an oracle candidate set.

### Structural experiment shape

Two fingerprint variants should be tested behind the same interface:

- B1-style multiscale role descriptors paired through typed directed paths; and
- B2-style monotone role/path shingles with optional rare-tail triples.

Each posting retains `(thought_id, endpoint_a, endpoint_b, feature_version)`.
Query collisions propose endpoint correspondences. A candidate receives a
structural score only from an IDF-weighted mutually injective consistent subset;
generic hashes above the document-frequency policy are skipped. Fine/coarse and
semantic/structural projections remain separate records.

### Output contract

```text
candidate_id
channel_scores: {content, knowledge_about, knowledge_complement, structural}
channel_ranks
seed_correspondences: [(query_node, candidate_node, support, channel)]
usable_query_evidence
index_version / feature_version / corpus_snapshot
```

Verification may ignore seeds and must independently adjudicate the mapping.

## Evidence

- R0-B1: relational constellation fingerprints survived paraphrase and domain
  substitution in a small pilot and sharply rejected a rewired graph.
- R0-B2: independent two-channel convergence plus explicit entropy and
  posting-skew accounting; structural M1/M3/M4 are falsifiable.
- R0-H: generic motif collision and the lack of a graph equivalent to a simple
  one-dimensional Shazam time-offset bin.
- R0-E: `about` versus `requires` enables same-domain and complementary recall
  without pretending to be structural analogy.
- R0-G: retrieval and oracle-verifier evaluation must be separated, with
  structure-over-words comparisons and per-family recall.

Exact input artifacts and commit provenance are recorded in
[R0 Synthesis](../../research/reviews/R0_SYNTHESIS_parshkov-openai-gpt5-codex-s7d3.md).

## Alternatives Considered

### Promote structural fingerprints immediately

Rejected for v0.1. The entropy calculation and generic-motif counterexample are
material, and no corpus experiment has shown that DF suppression retains the
rare analogical signal it removes.

### Kill structural retrieval permanently

Rejected. B1 shows a plausible correspondence-bearing design, B2 defines
concrete promotion/falsification metrics, and content-only retrieval cannot
discover disjoint-domain analogies by design. Shadow execution obtains evidence
without making an unsupported product claim.

### One blended semantic/structural score

Rejected. It hides whether words or relations retrieved a pair and makes the
defining paired hard negative uninterpretable.

### Whole-graph embedding, GNN, WL equality, MinHash-only, or exact graph search

Rejected as the primary structural candidate path. They respectively discard
correspondence, require training/data, are brittle to edits, lose endpoint
alignment, or perform verification before retrieval.

## Consequences

- v0.1 prioritizes an honest, testable verifier over an unproven promise of
  serendipitous global analogical discovery.
- Cross-domain candidates absent any content/user/oracle bridge may be missed
  until the structural channel is promoted.
- Retrieval scores remain mode/channel-specific and cannot be presented as the
  final resonance score.
- Index materializations are derived, versioned, and rebuildable; semantic
  buckets and fingerprints do not enter Thought DNA.
- Structural postings retain endpoints, increasing storage but preserving the
  only evidence useful for coherent voting and seeded verification.
- Corpus-wide DF and stop-motif policies are snapshot state; incremental index
  changes must record the snapshot/version.

## Benchmark / Validation

The structural channel is promoted only if one frozen configuration passes all
of these gates without tuning on gate packs:

1. **Extraction prerequisite:** duplicate extractions pass Benchmark v0.1's
   self-match thresholds; otherwise fingerprint stability is uninterpretable.
2. **Structure over words:** SOW at least `10/12`, with ties failing.
3. **Cross-domain recall:** structural-only Recall@20 at least `0.50` and each
   gate cross-domain family Recall@5 at least `4/6`.
4. **Generic-motif precision:** with the full descriptor, distance, DF/IDF, and
   consensus machinery enabled, the intended analogue outranks every
   full-constellation generic distractor in each reviewed motif pack; no tied
   posting-list result counts.
5. **Hard-negative control:** reversal, polarity, intent, and global-conflict
   families each have at most `1/6` false positives after coherent voting.
6. **Skew/scale:** touched postings grow sublinearly from `10^3` to `10^5`
   synthetic distractors under the fixed query budget; p95, maximum posting
   list, skipped-evidence fraction, recall, and index bytes are all reported.
7. **Determinism:** identical corpus snapshot and feature version reproduce
   ranked IDs, scores, and seeds.

Promotion does not establish one-million-corpus performance. That claim needs a
separate million-ID replay with index size, build time, p50/p95, and Recall@K.

## Known Failure Modes

1. Generic causal motifs consume nearly all lexicon-free structural entropy.
2. DF filtering removes exactly the cross-domain motif needed for recall.
3. Semantic bucket boundaries turn paraphrases into exact-hash misses.
4. Role or relation extraction drift destroys every feature touching an item.
5. Granularity changes alter path lengths and local neighborhoods.
6. Repeated/symmetric motifs yield several incompatible endpoint maps.
7. Partial fragments are penalized unless containment, not symmetric Jaccard,
   is used.
8. Corpus growth changes DF thresholds and rank order.
9. A semantic content path misses genuinely disjoint-domain analogies.
10. Knowledge entity linking creates false same-domain or complementary hits.

## Conditions for Reconsideration

- Promote a structural variant after every gate passes.
- Demote or kill it if recall requires reading effectively linear posting mass,
  generic motifs cannot be ranked, or independent extraction breaks self-hit.
- Reconsider content-only defaults if a different deterministic index supplies
  correspondence-bearing, high-entropy cross-domain features on the frozen
  benchmark and scale replay.
- Change channel fusion only through a new ADR that preserves per-channel
  observability.

## Related Research

- [R0 Synthesis](../../research/reviews/R0_SYNTHESIS_parshkov-openai-gpt5-codex-s7d3.md)
- [Thought DNA v0.1](../THOUGHT_DNA_v0.1.md)
- [Invariance Specification](../INVARIANCE_SPECIFICATION_v0.1.md)
- [Benchmark v0.1](../../benchmark/R0_BENCHMARK_v0.1.md)
