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

Persistence is a rebuildable JSON snapshot (postings + DF + graph ids).
