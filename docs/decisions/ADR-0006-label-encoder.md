# ADR-0006 — A local label encoder beside the lexicon

Status: **accepted** (2026-09-06)
Supersedes: nothing. Extends ADR-0004 (concept-aligned analogy).

## Context

The semantic layer of engine 0.2 is a hand-written lexicon of about 760
phrases plus a stemmer and character trigrams (`src/semantics`). It is
deterministic, inspectable and English-only, and it was calibrated on a
benchmark whose graphs were written by the same agents that wrote the lexicon.

Measured on real thoughts (a solo sailing passage, a plasma lens, a team under
deadline pressure) it is nearly blind:

| pair | lexicon |
| --- | --- |
| single-handed fatigue / sleep deprivation | 0.03 |
| wind vane self-steering / autopilot | 0.00 |
| rework / repeat defects | 0.07 |
| plasma column / ion beam focusing | 0.00 |

The consequence reached the verdict: the same trip described twice in
different words came back **negative at structural 1.00**, because the
"template coincidence" rule (ADR-0004) demands concept support before a
different-vocabulary pair may be called an analogy, and the lexicon could give
none. Two real people with the same shape saw each other as "not a
resonance" while seven seeded demo personas, written with the lexicon's
vocabulary, matched at 0.94. Russian labels scored 0.0 against everything.

PR #194 made the product refuse non-Latin labels rather than promise a search
that could never return; it named the real fix as "a semantic layer that
reads more than English".

## Decision

Add a **local sentence encoder for labels** (`src/semantics/neural.py`),
opt-in through `RESONANCE_EMBEDDER=<model directory>`:

- multilingual-e5-small exported to ONNX (quantised, ~118 MB), run on the CPU
  by `onnxruntime`, one label at a time, about 6 ms a pair, cached;
- the cosine between two label vectors is rescaled over the range that carries
  information (0.78–0.93 on this model; unrelated pairs sit at 0.75–0.79) and
  fused into `similarity.compare` as one more signal: it raises `concept`, and
  raises `surface` when the two labels are nearly the same; it never lowers a
  signal the lexicon gave;
- in scoring, concept coverage stays the lexicon's: the encoder raises
  `concept` on pairs the lexicon already speaks about and raises the semantic
  and surface signals everywhere, but cannot by itself manufacture an
  analogy between templated labels it happens to find alike (tried: it
  broke the analogy-over-coincidence gate); the frozen benchmark gates hold
  with or without it;
- retrieval, alignment, contradiction, the verdict and every threshold are
  unchanged;
- the engine identity (`/api/product/health` → `engine.label_encoder`) names
  the encoder, and a server told to load one refuses to start if it cannot.

Measured with the encoder on the same thoughts: the same trip in different
words → **direct**; solo Pacific against solo Atlantic → analogical; a part of
the system against the whole → approximate; a same-words-wrong-structure trap
→ negative; Russian labels against their English paraphrase → related (0.4–0.6).

## Why this does not break the principle

PRINCIPLES.md §3: LLMs are not the core matching engine. An embedding model is
not asked whether two people are compatible and does not see a thought. It
maps one short label to one vector, deterministically for a given file, and
the comparison stays a cosine that anyone can recompute. The structural
machinery is untouched and is still what decides.

## Consequences

- The lexicon stays the default and the frozen reports describe it; the
  encoder is a different engine identity and its own gate report should be
  frozen once real, human-labelled pairs exist (ADR-0005 remains open).
- The Docker image can bake the model in (`--build-arg
  RESONANCE_EMBEDDER_MODEL=Xenova/multilingual-e5-small`); the deployment
  turns it on with one variable. Memory cost is about 300 MB resident.
- Labels may now be written in any language the model reads; the product's
  refusal of non-Latin labels (#194) should be lifted when the encoder is
  active.
- The farmer-and-team-lead example that used to headline the page is not
  recovered by the encoder (its labels are genuinely unrelated words); it was
  a curiosity, not the promise, and the page no longer makes it.
