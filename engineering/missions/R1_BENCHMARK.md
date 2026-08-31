# R1-BENCHMARK — Frozen Benchmark v0.1 implementation

Issue: #39

## Objective
Turn the accepted benchmark contract into executable fixtures, schemas, runner, hashes and non-compensating gate reports.

## Prerequisites
R0-SYNTHESIS ACCEPTED. May develop beside R1-SCHEMA but final fixtures must validate against accepted schema.

## Ownership
`benchmark/`, benchmark runner/reporting tests. Do not tune engine algorithms here.

## Required outputs
- calibration and immutable gate packs
- machine-readable graph/pair/extraction fixtures and gold mappings
- analogy, complementarity, partial/granularity, same-words/wrong-structure, generic motif, polarity, extraction-noise and E1-derived cases
- deterministic runner, manifest hash and freeze policy

## Acceptance
Use issue #39. Emit per-family metrics and pipeline-stage attribution. Never rewrite gate gold to accommodate the current engine.