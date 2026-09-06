# R0-G — Resonance Benchmark and Falsification

Read `research/R0_MASTER_BRIEF.md` and `research/MISSION_CONTRACT.md` first.

## Decision question

What is the smallest scientifically useful benchmark that can tell us whether Resonance detects structure rather than merely words or topics?

## Required benchmark families

### Positive

1. paraphrase
2. vocabulary substitution
3. irrelevant branches added
4. partial graph / missing nodes
5. different granularity
6. same-domain structural match
7. cross-domain causal analogy

### Hard negative

8. same vocabulary, different relational structure
9. same topic, different intent
10. locally similar motifs with globally inconsistent alignment
11. generic/common graph patterns
12. accidental semantic similarity

### Complementary

13. one branch ends where another begins
14. same problem with disjoint but useful knowledge/method branches

## Resolve

1. Dataset size appropriate to a same-day MVP.
2. Which cases should be synthetic transformations and which manually authored gold pairs?
3. Label format for direct, approximate, analogical, complementary, and negative pairs.
4. Metrics including retrieval recall@K, resonance precision, node-correspondence accuracy, transformation robustness, and false-positive rate.
5. A PASS/FAIL threshold for the first fingerprint+verifier hypothesis.
6. How to stop the benchmark from rewarding semantic similarity alone.
7. How to preserve enough examples for later regression testing.

## Constraint

The first useful benchmark should be implementable in <=3 hours. It is the measuring instrument for R0, not a publication-scale dataset.