# Migration from Benchmark v0.1 to v0.2

## Why a new version

Independent repeat R0-D-REPEAT-S7D3 (PR #55) showed that frozen v0.1 cannot
independently measure `false_meaningful_contractions == 0`:

- 8 generated `transparent_granularity` positives
- 0 explicit negative-contraction cases
- no gold `meaningful_nodes`, `must_preserve_nodes`, or `forbidden_edge_path_matches`
- `runner.py` sums a prediction-supplied `false_contractions` integer

An engine can report `0` and pass regardless of its mappings.

## What v0.1 remains

`benchmark/r0-v0.1/` is frozen historical evidence. This version:

- does not edit v0.1 JSONL, hashes, schemas, or runner behavior
- does not relabel v0.1 gold to make a later engine pass
- does not claim that v0.1 research results are invalid

v0.1's other gates (SOW, polarity, E1, scale, extraction) are unchanged.

## What engines must emit for v0.2

Predictions must include structured `edge_path_matches` with canonical query
relation IDs, candidate relation IDs, and realized node IDs. A leftover
`false_contractions` integer may be present; the v0.2 gate ignores it.

## Overlay on frozen v0.1 positives

The v0.2 evaluator can score v0.1 `transparent_granularity` gold paths
read-only. Licensed v0.1 paths still derive zero false contractions. Because
v0.1 has no preservation gold, that overlay **cannot** catch cheaters on the
frozen bundle. Catching cheaters requires the v0.2 negatives.

## Independent review

`meaningful_mediator` (`V02-04`) is the only required manual gold item. It is
machine-similar to `transparent_one_step` and is distinguished only by gold
preservation fields. The fixture author must not approve it.
