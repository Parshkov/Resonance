# R5 — Resonance engine facade

`ResonanceEngine` composes the accepted components behind the frozen
`EngineFacade` protocol, with no MCP anywhere:

```text
context ──ingest──▶ CueExtractor (R2) ──▶ ThoughtGraph
manual dict ──ingest_manual──▶ same validator, kind=manual
graph ──index──▶ InMemoryThoughtStore + InvertedCandidateIndex (R3)
graph ──find(mode,k)──▶ retrieve ──▶ MultiRelFGWVerifier (R4) per candidate
                                └─▶ ResonanceHit(candidate, verification)
compare / explain / get           per the protocol
```

Persistence is a **bound engine snapshot** (`ResonanceEngine.dump/load`):
`store.json` + `index.json` + `manifest.json`. The manifest records engine,
interface, schema, extractor, index, feature, and verifier versions plus the
corpus snapshot and thought ids. Load rejects mixed store/index pairs,
tampered versions, and snapshot mismatch. `find()` fails closed if an index
candidate is absent from the bound store. Do not load the two files independently.

## Frozen v0.1 benchmark (two labelled paths)

`tests/engine_benchmark_e2e.py` indexes all 136 graphs and, for every frozen
pair:

1. **Real retrieval rank** — `candidate_index.query` with tie-aware
   `channel_ranks`. A candidate absent from the (tie-expanded) top-k is a
   retrieval miss (`rank = 10^6`).
2. **Oracle-inclusion verification** — the harness then verifies the
   evaluator-selected `candidate_graph` even on a retrieval miss, so the
   verification column isolates the verifier. That column is **not** a
   no-oracle `find()` traversal.

Committed report: `reports/r0-v0.1-end-to-end.json` (volatile timings stripped).
`overall_status: fail`.

Stage-attributed outcome, preserved rather than compensated:

- **Oracle-inclusion verification column passes its owned gates** — SOW 12/12,
  node-pair F1 1.0, directed-typed edge accuracy 1.0, precision 1.0, negative
  FPR 0.0, polarity rejection 1.0, deterministic replay, p95 within budget.
  The v0.1 `false_meaningful_contractions` gate also reads "pass", but that
  gate sums the harness's self-reported `false_contractions: 0` (the audit
  gap Benchmark v0.2 exists to close) -- it is NOT an independently derived
  contraction result.
- **Retrieval recall fails** on `partial_graph`, `transparent_granularity`,
  `modest_extraction_error` (recall@5 = 0; overall 0.727 < 0.85) because
  perturbed positives sit past a 48–71 rank-1 clone class (next distinct
  rank ~72). Recorded on #41; not compensated.
- **Verifier classification:** all 6 gate `vocabulary_substitution` pairs are
  retrieved at rank 1 but classified `analogical` against gold `approximate`.
  Scoring thresholds are not changed here.
- `extraction_prerequisite`, `structural_e1_matrix`, `structural_scale_replay`
  stay `not_evaluated` (R2 frozen-16 gap; E1/scale are R3-scope / PR #66).

Requires Python ≥ 3.10 (interfaces contract).
