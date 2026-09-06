# Extraction v0.1

Deterministic, span-grounded `context → ThoughtGraph`. The matcher never
calls a model. An LLM is optional at the boundary and is not required here.

v0.1 ships a **cue extractor**: explicit lexical relation cues only. Implicit
causation without a cue is abstained. Every extracted node and edge has an
exact source span. Objects below the drop threshold are deleted, not guessed.

Within one extraction, nodes with the same case-folded label are unified
(span lists are unioned). That is conservative identity, not coreference:
"heat" and "heat accumulation" stay distinct. Modality is read from the
cue's sentence, not a character window that crosses `.!?`. Reversed-cue
argument windows drop leading/trailing be-verbs (`Failure is` → `Failure`).

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

## v0.2 (ADR-0004)

~90 connectives in seven relation types with direction and confidence;
sentence/clause segmentation; noun-vs-verb disambiguation of ambiguous cues
("the speed limit" vs "backoff limits retries") with number agreement;
subject resolution for relative clauses, pronouns and coordinated predicates;
coordinated objects; sentence-initial "Because X, Y"; node unification by stem
set; roles from the lexicon then from graph position; clause-scoped negation
and modality; the context is PII-scrubbed before extraction. Evaluated on
`benchmark/extraction-v0.2` (`src/extraction/reports/extraction-v0.2-prose.json`).
Cue-free prose still yields an empty graph with an abstention, never invented
structure.
