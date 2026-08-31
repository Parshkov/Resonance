# Candidate Retrieval with Gated Multi-Scale Structural Fingerprints

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

The first submitted version of this ADR kept structural retrieval shadow-only.
Post-submit PR #36 then executed the B review's missing E1 kill test with the
full design. MULTI descriptors passed across two synthetic filler worlds,
tested sizes, and four seeds; role-only descriptors failed at `N=10000` in the
rich world. The experiment also showed a polarity-flipped near-duplicate
outranking the noisy true analogue. This revision records that evidence change
instead of erasing the earlier uncertainty.

## Decision

Use three independent candidate channels and expose their scores separately:

1. **content channel:** BM25 and/or an existing versioned semantic
   representation over node labels/source text for paraphrase and same-domain
   recall;
2. **knowledge channel (when annotated):** IDF-weighted posting lists
   over specific `knowledge.about` IDs and directional
   `query.requires -> candidate.about` joins; and
3. **structural channel (included in v0.1 behind the R0-G gate):** sparse
   multi-scale landmark-pair fingerprints with IDF, a hard
   document-frequency cutoff, a fixed query budget, coherent injective endpoint
   voting, and no semantic bits blended into the structural score.

The candidate service returns the deduplicated union, channel ranks/scores, and
optional seed correspondences. Every structural candidate is marked
`requires_structural_verification=true` and `polarity_reliable=false`; retrieval
is recall-oriented and never makes a user-visible resonance decision. The
channel is an explicit v0.1 component, but its product/corpus-scale claims remain
blocked by the gates below.

### Structural v0.1 shape

MULTI is mandatory and combines both descriptor scales:

- `D0`: stable controlled functional role; and
- `D1`: one round of directed, relation-typed WL neighborhood refinement.

Pair landmark descriptors through typed directed paths of length at most three
and include a distance bucket. D0 supplies edit survival; D1 supplies the
discrimination that E1 showed role-only D0 lacks at scale. Neither scale may be
shipped alone. Rare-tail triples and coarse relation-family projections remain
optional benchmark ablations, not v0.1 requirements.

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
requires_structural_verification
polarity_reliable
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
- R0-B E1 / PR #36: MULTI passes the full-design kill test in rich and
  chain-saturated synthetic worlds; D0 fails in the rich `N=10000` control;
  polarity inversion outranks the true noisy analogue; rich-world margin is
  thin. In the local synthesis reproduction, rich-world touched postings were
  216, 819, and 1,834 at `10^3`, `10^4`, and `3*10^4` items. E1 uses a toy
  role/relation inventory that includes `increases`, `enables`, and `precedes`,
  so it validates mechanics but does not replace a Thought-DNA-native gate.

Exact input artifacts and commit provenance are recorded in
[R0 Synthesis](../../research/reviews/R0_SYNTHESIS_parshkov-openai-gpt5-codex-s7d3.md).

## Alternatives Considered

### Keep structural fingerprints shadow-only

This was the initial submitted decision and is superseded by E1. The full
converged machinery retained rare constellation branches and passed its stated
kill rule. The remaining uncertainty limits scale claims; it no longer justifies
excluding the channel from the v0.1 architecture.

### Kill structural retrieval permanently

Rejected. B1 supplies the correspondence-bearing design, B2 supplies entropy
controls, and E1 executes the combined falsifier. Content-only retrieval cannot
discover disjoint-domain analogies by design.

### Role-only structural keys

Rejected. E1's D0 variant fails across four seeds at `N=10000` in the rich
world. D1 rescues discrimination but is less robust to edits, so MULTI is the
minimum allowed configuration.

### Treat a structural retrieval rank as polarity-safe

Rejected. E1's one-edge `causes -> prevents` variant ranks above the true noisy
analogue in every reported configuration. Retrieval must carry the candidate to
the verifier, which hard-rejects sign/direction conflicts.

### One blended semantic/structural score

Rejected. It hides whether words or relations retrieved a pair and makes the
defining paired hard negative uninterpretable.

### Whole-graph embedding, GNN, WL equality, MinHash-only, or exact graph search

Rejected as the primary structural candidate path. They respectively discard
correspondence, require training/data, are brittle to edits, lose endpoint
alignment, or perform verification before retrieval.

## Consequences

- v0.1 includes a deterministic route for cross-domain structural candidates,
  but does not turn E1's one-constellation result into a global recall claim.
- Multi-scale descriptors, DF/IDF state, endpoint postings, and consensus voting
  are required together; role-only deployments are non-conforming.
- Polarity-flipped near-duplicates may outrank true analogues during retrieval;
  every structural result must be verified before acceptance.
- Retrieval scores remain mode/channel-specific and cannot be presented as the
  final resonance score.
- Index materializations are derived, versioned, and rebuildable; semantic
  buckets and fingerprints do not enter Thought DNA.
- Structural postings retain endpoints, increasing storage but preserving the
  only evidence useful for coherent voting and seeded verification.
- Corpus-wide DF and stop-motif policies are snapshot state; incremental index
  changes must record the snapshot/version.

## Benchmark / Validation

The structural channel ships as a v0.1 capability only if one frozen MULTI
configuration passes all of these gates without tuning on gate packs:

1. **Extraction prerequisite:** duplicate extractions pass Benchmark v0.1's
   self-match thresholds; otherwise fingerprint stability is uninterpretable.
2. **Structure over words:** SOW at least `10/12`, with ties failing.
3. **Cross-domain recall:** structural-only Recall@20 at least `0.50` and each
   gate cross-domain family Recall@5 at least `4/6`.
4. **E1 regression:** with the full descriptor, distance, DF/IDF, and
   consensus machinery enabled, the intended analogue outranks every
   full-constellation generic distractor in the 12-case matrix: the default seed
   at `10^3`, `10^4`, and `3*10^4` plus three additional seeds at `10^4`, each
   in both E1 worlds. D0-at-scale remains a required failing control; no tied
   result counts.
5. **DNA-native companion:** repeat the same design with Thought DNA v0.1's
   exact role and relation enums, or record a reviewed versioned projection;
   the noisy analogue must still outrank every generic distractor.
6. **Polarity division of labor:** the polarity-flip retrieval case is retained
   and flagged unreliable; the end-to-end verifier rejects it before acceptance.
   Reversal, intent, and global-conflict families each have at most `1/6`
   end-to-end false positives.
7. **Skew/scale:** touched postings grow sublinearly from `10^3` to `10^5`
   synthetic distractors under the fixed query budget; p95, maximum posting
   list, skipped-evidence fraction, recall, and index bytes are all reported.
8. **Determinism:** identical corpus snapshot and feature version reproduce
   ranked IDs, scores, and seeds.

Passing these gates does not establish one-million-corpus performance. That
claim needs a separate million-ID replay with index size, build time, p50/p95,
and Recall@K.

## Known Failure Modes

1. Generic causal motifs consume nearly all lexicon-free structural entropy.
2. DF filtering removes exactly the cross-domain motif needed for recall.
3. E1's toy-only role/relation entropy disappears under Thought DNA's smaller
   extractable vocabulary.
4. A polarity-flipped near-duplicate outranks the intended analogy in retrieval.
5. Semantic bucket boundaries turn paraphrases into exact-hash misses.
6. Role or relation extraction drift destroys every feature touching an item.
7. Granularity changes alter path lengths and local neighborhoods.
8. Repeated/symmetric motifs yield several incompatible endpoint maps.
9. Partial fragments are penalized unless containment, not symmetric Jaccard,
   is used.
10. Corpus growth changes DF thresholds and rank order.
11. A semantic content path misses genuinely disjoint-domain analogies.
12. Knowledge entity linking creates false same-domain or complementary hits.

## Conditions for Reconsideration

- Accept MULTI as a product capability only after every gate passes.
- Remove or supersede the channel if recall requires reading effectively linear
  posting mass, generic motifs cannot be ranked, or independent extraction
  breaks self-hit.
- Reconsider the mandatory D0+D1 composition only with replacement evidence
  across the same edit-survival and scale-discrimination controls.
- Change channel fusion only through a new ADR that preserves per-channel
  observability.

## Related Research

- [R0 Synthesis](../../research/reviews/R0_SYNTHESIS_parshkov-openai-gpt5-codex-s7d3.md)
- [Thought DNA v0.1](../THOUGHT_DNA_v0.1.md)
- [Invariance Specification](../INVARIANCE_SPECIFICATION_v0.1.md)
- [Benchmark v0.1](../../benchmark/R0_BENCHMARK_v0.1.md)
