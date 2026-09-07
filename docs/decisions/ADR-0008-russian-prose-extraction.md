# ADR-0008 — Extraction reads Russian prose

Status: accepted, 2026-09-07. Extractor `0.2.0` → `0.3.0`.

## The asymmetry

Resonance matched Russian thoughts and could not accept one.

The *matching* side has been bilingual for two releases: lexicon 0.3.0 gave all
90 concept classes Russian forms, and ADR-0006 put a multilingual label encoder
(`multilingual-e5-small`) behind the semantic layer. The *extraction* side was
never touched. So the engine could measure the resonance between two Russian
thoughts perfectly well, and there was no way to put one into it.

Measured on the same reasoning written twice:

| | nodes | relations |
| --- | --- | --- |
| Russian | **0** | **0** |
| English | 5 | 3 |

A person writing in their own language got `validation_failed: 0 nodes, 0
relations`, followed by an instruction addressed to a language model. The owner
of this project is a Russian speaker; the product was unusable to him in it.

## Four things were English-only, and the cue table was the least of them

Adding connectives alone would have changed nothing:

1. **`WORD`** matched `[A-Za-z0-9]…` — **no Cyrillic token at all**. A matched
   cue would still have produced empty arguments. This was the deepest one.
2. **`SENTENCE_END`** required the next sentence to open with `[A-Z"'(\[]`, so
   Russian prose was one unbroken sentence and clause segmentation never ran.
3. **The cue table** — ~90 English connectives, no Russian.
4. **Stopwords, negation, modality, conditionals** — English word lists, so
   labels would have carried pronouns and prepositions and every hedge would
   have read as asserted fact.

`stems()` already handled Cyrillic, which is exactly what made this look
smaller than it was.

## Decision

Russian connectives live in their own table, `_CUE_TABLE_RU`, appended after
the English one. The two alphabets do not overlap, so no Russian pattern can
match English prose or the reverse. English extraction is therefore not merely
"still passing" but **byte-identical**: the gate reports the same twelve
figures before and after (`node_f1` 0.9333, `edge_f1` 0.9359, `role_accuracy`
0.6218, …).

Two things Russian needs that English does not:

- **Modal + infinitive.** «может привести к», «могут вызвать» is the ordinary
  hedged register. Without infinitive forms the whole register was invisible,
  and the first draft read «Короткие смены могут снижать число ошибок» as no
  relation at all.
- **The comma before «что».** Russian orthography requires it, and a comma is a
  clause break, so «показывают, что X» lost X entirely. English never meets
  this — "show that X" has no comma. The comma is written into those cues, and
  they are tried before the bare verb. For the same reason bare «что» is *not*
  a clause boundary, though English `that` is: English recovers via
  `AUX_AFTER_THAT`, and Russian drops the copula, so there is no auxiliary to
  recover on.

## What was deliberately not done

Both languages misread the same convoluted sentence in the same way: the left
argument of a final cue is taken from a distant clause rather than the adjacent
one. This is a pre-existing limit of clause selection on long multi-clause
sentences, **not** a Russian fault — verified by running the English
translation and getting the same wrong shape.

It is not fixed here, because fixing it would move frozen English figures and
this change's whole safety argument is that it does not. It is pinned in
`tests/test_russian_prose_extraction.py` so the parity is a decision on record
rather than a Russian-only fault discovered again later.

## Consequences

- Russian prose extracts. Measured across the seven relation types, six of
  seven test sentences parse correctly, including reversed direction on
  «потому что» and a two-link causal chain.
- The extractor version moves to `0.3.0`; `/api/product/health` reports it.
- Neither benchmark gate is keyed to the extractor version, so no recorded
  report needed regenerating.
- `ROADMAP` §5 (multilingual prose extraction) is closed for Russian. Every
  other language is still English-only, and the same four subsystems would
  need the same treatment.

## What would falsify this

A Russian corpus where extraction quality is materially worse than English on
equivalent prose. There is no Russian gold set — the 22 extraction cases are
English. Building one is the honest next step, and until it exists the claim
here is "Russian extracts and English did not move", not "Russian extracts as
well as English".
