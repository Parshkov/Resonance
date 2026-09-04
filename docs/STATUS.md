# Resonance — Status

Updated: 2026-09-04

## Where the project actually is

| layer | state | evidence |
|---|---|---|
| Thought DNA schema v0.1 | frozen, validated, canonical hashing | `src/graph`, `tests/test_thought_dna_schema.py` |
| Deterministic semantics (no LLM) | engine 0.2: lexicon + stems + relatedness | `src/semantics`, `tests/test_semantics.py` |
| Retrieval | structural + concept + content channels, IDF, verified re-ranking | `src/fingerprint`, `src/index`, `src/engine/reports/r0-v0.2-e2e.json` |
| Verification / scoring | FGW conditional gradient + scoring policy v0.2 | `src/alignment`, `src/scoring`, ADR-0004 |
| Extraction from prose | cue extractor v0.2, edge F1 0.94 on 22 prose cases | `src/extraction`, `benchmark/extraction-v0.2` |
| Benchmark | v0.2: 8 skeletons × 4 domains × 18 families, gate split untouched by tuning | `benchmark/r0-v0.2` |
| Product (MCP, WebMCP, OAuth, persistence) | deployed; one MCP vocabulary (`src/product/mcp_bridge.py`) | `src/product`, `ops/DEPLOY.md` |

## What is validated

- Same words / different structure → rejected (polarity flips are hard-rejected; full permutations raise `label_identity` contradictions).
- Different words / same abstract structure → `analogical`, on 8 skeletons × 3 other domains each, and on the hand-authored demo corpus.
- Same skeleton with concept-free labels (template coincidence) → `negative`.
- Partial, granular, paraphrased, permuted and extraction-noisy variants → retrieved in the top 5 among distractors and classified correctly.
- Prose → graph without an LLM for texts that carry explicit connectives; cue-free prose yields an honest empty graph.

## What is not validated

- Real user thoughts at scale: every benchmark graph is authored (by agents), not extracted from real conversations. Independent human review of the v0.2 gold is pending.
- Corpus scale 10^4–10^6: no replay beyond a few hundred graphs.
- Extraction of implicit causation (no connective) is abstained by design.
- Native WebMCP browser discovery on a hosted client (see `submission/RELEASE_MANIFEST.md`).

## Process notes

- Engine 0.1 gate reports under `src/*/reports/r0-v0.1-*.json` are kept as history; they were computed on the single-template v0.1 corpus and are not comparable with 0.2.
- Import-time monkey-patch modules (`review_hardening`, `review_alignment`) were folded into the classes they patched; behaviour is unchanged and now visible in one place.
- The second remote MCP server and its 15-tool vocabulary were removed; `src/remote/server.py` is a thin factory over the product server.

## Next falsification targets

1. A corpus of real extracted thoughts (consented) with two-human gold; compare engine 0.2 against a whole-thought embedding baseline.
2. Scale replay of the concept channel at 10^4–10^5 graphs.
3. Lexicon coverage audit on real labels; add classes only with two independent examples.
