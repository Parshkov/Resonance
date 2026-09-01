# Resonance Benchmark r0-v0.2

Versioned contraction-audit extension of Benchmark v0.1.

This bundle does **not** replace v0.1 and does **not** rewrite frozen v0.1
gold. It exists because v0.1's `false_meaningful_contractions == 0` gate
trusted a prediction-supplied integer.

## What changed

v0.2 gold records:

- `meaningful_nodes`
- `must_preserve_nodes`
- `forbidden_edge_path_matches`
- licensed `gold_edge_pairs` paths for transparent positives

The evaluator derives false contractions from submitted `edge_path_matches`
(and path-shaped `edge_mapping` entries) against that gold.
`verification.false_contractions` is ignored if present.

## Freeze state

Mechanical families are generated from the accepted invariance spec. The
`meaningful_mediator` case is a gold judgment and remains
`pending` independent review. The author cannot self-approve it.

Contraction-audit gates can still be measured while that review is pending.
`independent_gold_review` stays fail until an independent reviewer approves
`V02-04`.

## Commands

```bash
python3 benchmark/r0-v0.2/build_fixtures.py
python3 benchmark/r0-v0.2/runner.py validate
python3 benchmark/r0-v0.2/runner.py evaluate --predictions /path/to/predictions.jsonl
python3 -m unittest tests.test_benchmark_v0_2 -v
```
