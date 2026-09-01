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
