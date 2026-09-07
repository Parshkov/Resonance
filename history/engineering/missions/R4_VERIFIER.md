# R4-VERIFIER — Typed partial graph alignment and scoring

Issue: #42

## Objective
Implement expensive structural verification that produces a partial mapping, typed/directed structural evidence, contradictions and explainable scores.

## Prerequisites
R0-SYNTHESIS, R1-SCHEMA and R1-INTERFACES ACCEPTED. Use R1-BENCHMARK as the gate. Retrieval seeds are optional inputs, never correctness requirements.

## Ownership
`src/alignment/`, `src/scoring/`, structural explanation payloads and verifier tests.

## Required outputs
- accepted v0.1 proposal solver (multi-relational FGW if synthesis retains it)
- discrete partial one-to-one mapping
- exact typed/directed rescore
- hard polarity/sign and causal-direction rejection
- guarded edge-to-path matching for transparent granularity
- at least one unseeded restart path
- QAP/RRWM gate candidate/fallback
- separate score components and stable mapping/contradiction explanation

## Acceptance
Use issue #42 and the accepted verifier bake-off. Cross-domain structural matches must survive low semantics; polarity/reversal negatives must fail. Record mapping quality, typed-edge quality, versions and latency.