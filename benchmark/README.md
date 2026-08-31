# Resonance Benchmark

This directory will contain the smallest falsifiable benchmark for the core algorithm.

The benchmark must separate structural signal from surface semantic similarity.

Required categories:

## Positive

- paraphrase
- vocabulary substitution
- irrelevant branch insertion
- partial observation
- different granularity
- same-domain structural match
- cross-domain causal analogy

## Hard negative

- same vocabulary, different structure
- same topic, different intent
- locally similar motifs with globally inconsistent alignment
- generic/common graph patterns
- accidental semantic similarity

## Complementary

- one branch ends where another begins
- same problem with disjoint useful knowledge

Primary metrics should include retrieval recall@K, resonance precision, node-correspondence accuracy, robustness under controlled transformations and false-positive rate.

Research Mission G has returned and the R0 synthesis records the proposed
[Benchmark v0.1 contract](R0_BENCHMARK_v0.1.md). Its fixture manifest is frozen
only after the authoring, validation, and independent-review steps in that
contract; the synthesis document alone does not invent benchmark results.

The executable authored candidate is in [`r0-v0.1/`](r0-v0.1/README.md). Its
hashes and runner are frozen, but manual gold remains visibly pending
independent review; that state cannot produce a passing gate report.
