# Resonance Benchmark r0-v0.1

This directory is the executable form of the accepted Benchmark v0.1
contract. It freezes authored inputs and gold separately from any engine
implementation. It does not contain an extractor, retriever, verifier, or
scoring algorithm, and it makes no real-corpus or million-item scale claim.

## Current freeze state

`manifest.json` records `independent_review_complete` after the independent
gold review in
`research/reviews/R1_BENCHMARK_gold_review_parshkov-xai-grok46-k3e8.md`.
Manual analogy, intent, generic-motif, complementary, and extraction-reference
judgments are approved by `parshkov-xai-grok46-k3e8`, not by the fixture
author. `runner.py validate` reports `gate_execution_ready: true` only while
that ledger remains complete.

The review also corrected a generator defect: `vocabulary_substitution` no
longer copies the cross-domain analogy label set. Rejected or later-changed
cases require a new benchmark version after this freeze; gate gold is never
relabelled to make an engine pass.

## Contents

- `graphs.jsonl`: 136 engine-safe graph wrappers. The only fields are a public
  benchmark graph ID and valid Thought DNA v0.1.
- `pairs.jsonl`: 128 gold pair records: 8 packs × 16 families. `C01`–`C02` are
  calibration; `G01`–`G06` are immutable gate candidates.
- `extraction_runs.jsonl`: two source/reference extraction observations per
  pack, kept outside the graph input corpus.
- `e1_cases.jsonl`: the 12-case two-world/size/seed DNA-native E1 companion
  matrix. It requires D0, D1, and MULTI, includes generic, polarity, and
  direction controls, and records synthetic filler recipes.
- `schema/`: Draft 2020-12 schemas for fixtures, predictions, and reports.
- `config/evaluation-v0.1.json`: accepted non-compensating thresholds.
- `manifest.json` and `manifest.sha256`: byte hashes, counts, freeze state, and
  provenance.
- `build_fixtures.py`: deterministic, reviewable corpus generator.
- `runner.py`: fixture validator and evaluator for external predictions.

The legacy E1 script remains unchanged at
`../../research/experiments/R0_E1_fingerprint_discrimination.py`. Its published
timings and thin ~0.009 rich-world margin are provenance, not thresholds. The
DNA-native companion here uses only the seven accepted relation enums. R3 must
still emit the actual E1 and 10^3–10^6 scale-replay measurements through the
provided prediction schemas; until supplied, the runner reports those
structural sub-gates as `not_evaluated`.

## Gold isolation

Graph engine input is the projection:

```json
{"benchmark_graph_id": "G01-Q", "thought_dna": {}}
```

Extraction engine input is only:

```json
{"extraction_case_id": "G01-X1", "input": {"text": "...", "sha256": "..."}}
```

Pair labels, mappings, rationales, review state, and extraction reference graphs
stay in the evaluator process. `runner.py validate` checks the graph wrapper is
closed and recursively rejects benchmark-gold keys inside Thought DNA.

## Commands

Python 3.12 and the repository's dependency-free `src.graph` validator are
sufficient.

```bash
python3 benchmark/r0-v0.1/build_fixtures.py
python3 benchmark/r0-v0.1/runner.py validate
python3 benchmark/r0-v0.1/runner.py evaluate \
  --predictions /path/to/pairs.predictions.jsonl \
  --extraction-predictions /path/to/extraction.predictions.jsonl \
  --e1-predictions /path/to/e1.predictions.jsonl \
  --scale-predictions /path/to/scale.predictions.jsonl \
  --output /path/to/report.json
python3 -m unittest discover -s tests -v
```

Rebuilding is deterministic. Validation fails if generated JSONL differs from
the generator, a tracked byte/hash differs from the manifest, a graph violates
Thought DNA, pack/family topology changes, family 10 loses its required
2-polarity/2-direction/2-rewire gate allocation, or the E1 matrix/vocabulary
changes.

## Prediction and report contract

One pair prediction is required for every `case_id`. It contains retrieval rank
and separate channel scores, verifier class and mappings, contradictions/hard
rejection, component vector, latency, and a deterministic replay projection.
Structural retrieval must declare `polarity_reliable=false` and
`requires_structural_verification=true`.

The report contains:

- per-family Recall@5, classification, mapping, edge, and false-positive data;
- SOW, precision, FPR, mapping/edge accuracy, latency, polarity rejection, and
  extraction metrics;
- a single stage attribution per gate case (`retrieval_miss`, verifier class,
  mapping, false-positive, polarity, replay, or pass); and
- one status per mandatory gate.

The E1 adapter requires all 12 MULTI margins/ranks, retrieval polarity flags,
verifier rejection, timings, postings and replay hashes. The scale adapter
requires both synthetic worlds at 10^3, 10^4 and 10^5; it checks that touched
postings grow more slowly than corpus size, Recall@20 is at least 0.50, and
replay hashes agree. Million-scale and extracted-distribution rows are reported
separately and are not inferred from the synthetic 10^5 gate.

`overall_status` is PASS only when every recorded gate is PASS. A macro average
cannot compensate for a polarity, negative-family, mapping, extraction,
independent-review, or deterministic-replay failure. Unsupported or absent E1
scale output remains visible as `not_evaluated` rather than being silently
treated as success.

## Provenance

- run: `R1-BENCHMARK`
- agent: `parshkov-openai-gpt5-codex-s7d3`
- sponsor: `Parshkov`
- provider/model: OpenAI, GPT-5-based Codex (exact deployed snapshot not
  exposed)
- runtime used to author and validate: Python 3.12 standard library plus the
  accepted `src.graph` Thought DNA validator
- source contracts: accepted R0 synthesis, Benchmark v0.1, Thought DNA v0.1,
  Invariance Specification, retrieval/verification ADRs, and scoring contract

Fixture concepts and mappings are synthetic authored benchmark material. They
must not be represented as observed production data.
