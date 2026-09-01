# R1-BENCHMARK-v0.2 — Independently auditable false-contraction gate

Issue: #56

## Objective
Version Benchmark v0.1's `false_meaningful_contractions == 0` gate so an
engine cannot pass by self-reporting zero. Derive false contractions from
preservation gold and submitted edge/path mappings.

## Prerequisites
R1-BENCHMARK ACCEPTED. Do not mutate frozen v0.1 gold, hashes, or runner
behavior.

## Ownership
`benchmark/r0-v0.2/**`, contraction-audit tests. Read-only use of
`benchmark/r0-v0.1/**`.

## Required outputs
- negative contraction families: meaningful mediator, atomic mediator,
  branch/merge, mixed relation/sign, modality/assertion, path-length limit
- gold `meaningful_nodes`, `must_preserve_nodes`, `forbidden_edge_path_matches`
- evaluator-derived false-contraction counts
- tests that `false_contractions: 0` cannot obtain PASS when mappings violate gold
- deterministic manifest/config hashes
- migration note from v0.1
- freeze policy: author cannot self-approve required manual gold

## Acceptance
Use issue #56. A cheating prediction must fail. Transparent-granularity
positives must still pass under the same evaluator. Attribute contraction
failures to the verifier/mapping stage.
