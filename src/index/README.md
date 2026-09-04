# Candidate index v0.1

Three independent retrieval channels over Thought DNA:

1. **content** — BM25-like over node labels / source text
2. **knowledge** — IDF postings on `knowledge.about` plus directional
   `query.requires -> candidate.about`
3. **structural** — MULTI landmark-pair inverted index with DF cutoff,
   IDF weighting, and injective correspondence consensus

Default structural variant is MULTI. D0/D1 exist only as named ablations
for E1-style controls. Role-only keys are not the shipped query path.

Every `CandidateResult` is fail-closed: `polarity_reliable=false` and
`requires_structural_verification=true`. Retrieval never emits a semantic
node-pair mask.

Persistence is a rebuildable JSON snapshot of graphs, DF, versions, and
the DF/budget policy. `load()` restores that policy and rejects tampered
`index_version` / `feature_version` / `corpus_snapshot`.

Bulk indexing uses `build(graphs)` (one rebuild). Sequential `upsert`
remains correct but is quadratic; do not use it to load a large corpus.

Query instrumentation is on `index.last_query` (`postings_touched`,
`latency_seconds`, live/skipped keys, budget). Structural mode does not
scan the content corpus. The shipping query uses a 64-key rarest-live-key
budget.

Small corpora (n < 1000) use a 0.90 DF fraction so analogical keys are
not all killed by `min_df_cutoff=5`. Large corpora keep the 0.005 / 5
policy.

**Tie policy:** equal primary scores share competition min-rank.
`thought_id` is only a stable display order inside a tie, never a rank
key. `query(..., k=K)` returns every candidate whose primary rank is
`<= K`, so a tied-best group is not truncated by graph name. Rank- and
recall-consuming gates must read `channel_ranks`, not list position.

## v0.2 (ADR-0004)

Channels: `structural` (label-free keys), `concept` (lexicon keys), `content`
(BM25 over stems, normalised by the query self-score), `knowledge`. Keys are
IDF-weighted; a key is skipped only when more than 50% of a corpus (>= 20
graphs) carries it, so common motifs are down-weighted rather than dropped.
`analogical` mode ranks by the fused score 0.45·structural + 0.40·concept +
0.15·content; `structural` mode stays label-free. `motif_rarity(graph)` gives
the corpus-relative rarity of a skeleton for scoring. `channel_ranks["primary"]`
is the fused rank.
