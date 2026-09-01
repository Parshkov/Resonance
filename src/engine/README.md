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

Persistence composes from the parts: `store.dump/load` (canonical JSON) +
`candidate_index.dump/load` (R3's tamper-checked payload); a restored engine
reproduces `find` exactly (integration-tested).

## End-to-end benchmark result (frozen v0.1, no oracle)

`tests/engine_benchmark_e2e.py` builds the engine over all 136 graphs and asks
the index for every pair's REAL tie-aware candidate rank. Committed report:
`reports/r0-v0.1-end-to-end.json` (volatile timings stripped).

Stage-attributed outcome, preserved rather than compensated:

- **Verification column: every owned gate passes end-to-end** — SOW 12/12,
  node-pair F1 1.0, directed-typed edge accuracy 1.0, precision 1.0, negative
  FPR 0.0, polarity rejection 1.0, deterministic replay, p95 within budget.
  The v0.1 `false_meaningful_contractions` gate also reads "pass", but that
  gate sums the harness's self-reported `false_contractions: 0` (the audit
  gap Benchmark v0.2 exists to close) -- it is NOT an independently derived
  contraction result. The independently derived evidence is the v0.2
  contraction audit, which the verifier passes in both path configs (see
  PR #64's evidence trail).
- **Retrieval recall fails on exactly three positive families**
  (`partial_graph`, `transparent_granularity`, `modest_extraction_error`,
  recall@5 = 0; overall 0.727 < 0.85). Attribution: the frozen corpus packs
  ~17 structural near-clones per base, producing a 48–71-candidate tied-best
  class at rank 1; under competition ranking the next distinct score starts at
  rank ~72, so every *perturbed* positive is arithmetically outside recall@5
  regardless of retrieval quality. This is the corpus-degeneracy limit already
  recorded on #41 during R3 acceptance, now quantified end-to-end.
- `extraction_prerequisite`, `structural_e1_matrix`, `structural_scale_replay`
  stay `not_evaluated` (R2 discloses the frozen-16 gap; full E1/scale files are
  R3-scope, with the independent repeat PR #66 carrying a full matrix).

Requires Python ≥ 3.10 (interfaces contract).
