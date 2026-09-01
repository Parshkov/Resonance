# Extraction v0.1

Deterministic, span-grounded `context → ThoughtGraph`. The matcher never
calls a model. An LLM is optional at the boundary and is not required here.

v0.1 ships a **cue extractor**: explicit lexical relation cues only. Implicit
causation without a cue is abstained. Every extracted node and edge has an
exact source span. Objects below the drop threshold are deleted, not guessed.

Manual graphs use the same Thought DNA validator with `provenance.kind=manual`
and `extractor: null`.

Knowledge DNA IDs are `local:` slugs from explicit text; there is no
live-network hot path.

## Repeat-extraction F1

`repeat_extraction_f1` aligns nodes by `(role, spans, assertion, modality)`
and then scores typed edges through that alignment. Local `thought_id` /
`source_id` namespaced IDs are not identity.

## Frozen Benchmark v0.1 coverage

The 16 frozen `extraction_runs.jsonl` inputs are noun-phrase bags with no
explicit relation cues (`causes`, `prevents`, …). Cue-only extraction
therefore emits 0 nodes / 0 relations on that corpus. That is reported
coverage, not a vacuous pass of the extraction prerequisite.

Measure:

```text
python3 -m src.extraction.evaluate_v0_1
```

A non-vacuous repeat is the same cued sentence extracted under two
`source_id` values. The frozen gate is not claimed from empty/empty F1.
