# Candidate retrieval index

`CandidateRetrievalIndex` implements the accepted graph-level `CandidateIndex`
port without importing extraction, verification, scoring, or MCP modules.

It keeps four independent evidence channels:

- `structural`: D0+D1 path fingerprints, DF/IDF, a hard common-motif cutoff,
  a fixed 64-feature query budget, and mutually injective correspondence votes;
- `content`: token postings over node labels (and optionally source text);
- `knowledge_about`: exact Knowledge DNA `about` joins; and
- `knowledge_complement`: directional query `requires` to candidate `about`
  joins in complementary mode.

The union ranking uses the best explicit channel rank. It does not publish a
blended similarity. Every result carries per-channel scores/ranks, optional
seed correspondences, index/feature/config/corpus versions,
`requires_structural_verification=true`, and `polarity_reliable=false`.

Equal channel scores use competition/minimum rank: a 48-way tied-best group is
rank 1 for every member, never ranks 1 through 48 based on `thought_id`.
`query()` preserves the accepted hard `k` surface and reports whether its
cutoff split a tie. `query_with_diagnostics(..., include_cutoff_ties=True)`
widens the result through the complete cutoff group. Diagnostics expose both
the tied-best IDs and cutoff-tied IDs so callers cannot mistake lexical ID order
for retrieval evidence.

Use `query_with_diagnostics()` when postings touched, channel latency, selected
feature count, skipped evidence, posting skew, estimated index bytes, and the
deterministic replay hash are needed. `query()` remains compatible with the R1
interface.

`upsert()` modifies only the inserted graph's postings. Corpus snapshot hashing
is lazy, avoiding a full rebuild on every public insertion. `save()` writes an
integrity-hashed, rebuildable graph/config snapshot; `load()` rejects changed
policy, corpus, format, index, or feature metadata.

See `R3_REPEAT_M8K4_REPORT.md` for gate results and explicit limitations.
