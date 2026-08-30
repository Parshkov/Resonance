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

The benchmark definition is intentionally not frozen until Research Mission G returns.
