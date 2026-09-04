# Concept-Aligned Analogy, Multi-Skeleton Benchmark, and Verified Ranking

Status: accepted (engine 0.2); supersedes the classification policy and the
retrieval dead-key rule of ADR-0002 / ADR-0003, which otherwise stand.

Date: 2026-09-04

## Context

An independent assessment of the engine 0.1 chain (this ADR's provenance:
`agents/registry/parshkov-anthropic-fable51-uutj4x.md`) found four defects that
made the scientific claims of the README aspirational relative to the code:

1. **Structure was a role skeleton.** Fingerprints and affinity used only the
   nine node roles and seven relation types. Any two graphs with the same
   skeleton scored structural 0.888 and were classified `analogical`, whatever
   their content (verified: a battery fire, homework procrastination and
   sourdough baking were mutually "analogical").
2. **Semantics was token Jaccard.** No lexicon, stems or embeddings existed;
   a synonym was indistinguishable from a cross-domain analogy, and both were
   indistinguishable from a template coincidence.
3. **Benchmark v0.1 was one template.** All 136 graphs instantiate a single
   10-node skeleton with eight label sets; "cross-domain analogy" was a
   relabelling; calibration and gate splits were structurally identical; the
   engine 0.1 gate report already carried `overall_status: fail`.
4. **Retrieval was brittle and content-blind.** Exact hashed neighbourhoods
   dropped partial/granular/noisy positives out of the top 5, and the dead-key
   rule made any motif carried by more than 0.5% of a corpus unretrievable.

The red-team result of R0-H ("domain invariance *is* generic-motif
indistinguishability") was correct and had not been answered.

## Decision

1. **Deterministic label semantics without an LLM** (`src/semantics`): Porter
   stems, a hand-authored lexicon of ~115 abstract relational concept classes
   (accumulation, depletion, cascade, feedback, constraint, ...) with a soft
   relatedness table, domain-anchor classes that carry no analogical weight,
   and three separate signals per label pair: `surface` (same words),
   `concept` (same abstract notions), `domain` (same domain anchors). Role
   names themselves are never lexicon terms. An optional embedder seam exists
   for a local non-LLM encoder; the default is the lexicon.
2. **Concept channel in retrieval** (`src/fingerprint`, `src/index`): keys
   over (role, abstract class, typed path <= 2) beside the label-free
   structural keys; IDF weighting with a 50%-of-corpus stop-key rule instead
   of hard dead keys; BM25 over stems; fused primary rank
   (0.45 structural + 0.40 concept + 0.15 content) for the `analogical` mode;
   the `structural` mode stays label-free; corpus `motif_rarity` is exposed.
3. **Scoring policy v0.2** (`src/scoring`): affinity uses soft role
   compatibility and lexicon similarity; a mapping that aligns structure
   against an unmistakable label twin raises a `label_identity` contradiction
   (the project's central hard negative, "same words, different structure",
   now caught even for full permutations); role/coverage terms scale with
   relational evidence so a mapping with no preserved relation cannot reach
   the resonance threshold; the evidence gate is a geometric mean instead of a
   5-node/4-relation cliff; classification: surface or domain overlap ->
   direct/approximate; otherwise `analogical` requires concept alignment
   >= 0.25 (or a rare skeleton with weak concept support, only when a corpus
   is present); bare skeleton agreement is `negative` (template coincidence).
   Confidence is three-level (evidence mass, threshold margin, conflicts).
4. **Verified ranking with over-fetch** (`src/engine`): retrieval proposes
   4k (min 24) candidates, verification ranks them, the engine returns the
   best k by verified score plus hard-rejected candidates from the caller's
   retrieval window.
5. **Benchmark v0.2** (`benchmark/r0-v0.2`): eight distinct skeletons, four
   hand-authored domain instantiations each with concept-aligned slots,
   eighteen families including `template_coincidence`, `polarity_flip` and a
   partial cross-domain analogy; calibration (S1–S4) and gate (S5–S8) are
   different skeletons; thresholds were tuned on S1–S4 only.
6. **Extractor v0.2** (`src/extraction`): ~90 connectives with direction,
   clause segmentation, subject resolution, coordinated objects, roles from
   the lexicon then graph position, clause-scoped negation/modality, PII scrub
   before extraction; measured on `benchmark/extraction-v0.2` (22 prose cases).

## Evidence

| measure | engine 0.1 on Benchmark v0.2 (gate) | engine 0.2 (gate S5–S8) |
|---|---|---|
| positive Recall@5 among distractors | 0.08 | 1.00 |
| negative false-positive rate | 0.17 | 0.00 |
| template coincidence accepted as analogy | 4/4 | 0/4 |
| classification accuracy | 0.78 | 1.00 |
| polarity rejection | 1.00 | 1.00 |
| positive node F1 | 0.83 | 0.85 |

Reports: `src/engine/reports/r0-v0.2-baseline-engine-0.1.json`,
`src/engine/reports/r0-v0.2-e2e.json`. Extraction:
`src/extraction/reports/extraction-v0.2-prose.json` (edge F1 0.94, node F1
0.93, assertion 1.0, modality 0.97, PII leaks 0). The demo corpus analogies
(plasma lens vs. inbox overload, warehouse, traffic, irrigation, battery) are
recognised; unrelated demo sessions are not.

Of the eight v0.1 "cross-domain analogies", three are still analogical under
v0.2 (C01, C02, G01); the other five align by role only with no abstract
concept correspondence and are now `negative`. That is the intended contract
change: role agreement alone is not analogy.

## Alternatives Considered

- **Sentence-embedding model for labels.** Rejected as the default: adds a
  model dependency to a stdlib-only engine and makes decisions non-inspectable.
  Kept as an optional seam (`src/semantics/embedding.py`).
- **Hard concept threshold without coverage discount.** Rejected: lexicon
  silence on a slot is missing evidence, not evidence of difference; the mean
  over covered slots is discounted by sqrt(coverage) instead.
- **Keeping the v0.1 dead-key rule.** Rejected: a common human reasoning
  pattern is exactly what a person may want to find; IDF down-weighting keeps
  it retrievable.

## Consequences

- Analogy claims now depend on lexicon coverage. Coverage gaps degrade to
  `negative`, never to false positives. The lexicon is versioned and every
  change alters fingerprint/config hashes.
- `confidence` is no longer the constant `provisional`.
- Scores are not comparable with engine 0.1 reports.

## Benchmark / Validation

`python3 benchmark/r0-v0.2/runner.py` must exit 0 (all eight gates on
S5–S8). `python3 benchmark/extraction-v0.2/runner.py` must exit 0.
`tests/test_benchmark_v0_2.py` enforces both.

## Known Failure Modes

- Labels outside the lexicon (rare jargon) get no concept credit.
- Very small graphs (2 nodes, 1 relation) score at most ~0.4 of the
  evidence gate and rarely pass `T_STRUCTURE`; this is intended.
- Gold for Benchmark v0.2 and extraction-v0.2 is AI-authored; independent
  human review is still required before external claims.

## Conditions for Reconsideration

- A human-reviewed corpus of real extracted thoughts where the lexicon
  channel adds nothing over whole-thought embeddings.
- Corpus scale replay (10^4–10^5) showing the concept channel's posting lists
  are not sub-linear.

## Related Research

R0-B1/B2, R0-C1–C3, R0-H (both runs), the independent assessment in
`research/logbook/2026-09-04-engine-0.2.md`.
