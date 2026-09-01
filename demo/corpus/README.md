# R7 demo corpus — consented multi-session Thought DNA

Version: `resonance-demo-corpus/0.1`

This is **demo infrastructure**, not a production social graph and not a
claim of population-scale performance.

Each record is a consented session wrapping a manual Thought DNA document
that the accepted Resonance engine already understands. Matching still
happens in the engine. Topic, domain, cluster labels, display names, and
coarse locations are presentation metadata only.

## Layout

```text
demo/corpus/
  sessions.jsonl     committed seeded corpus
  manifest.json      hashes, cluster index, hidden ids
  manifest.sha256
  build.py           deterministic rebuild
  validate.py
  discovery.py       consent filter + engine join
  VOLUNTEER.md       how to add a consented session later
```

Schema: `schemas/demo-corpus-0.1.schema.json`.

## Rebuild / validate

From the repository root:

```bash
python3 -m demo.corpus.build
python3 -m unittest tests.test_demo_corpus -v
```

Rebuild is deterministic: a second run must leave `sessions.jsonl` byte-identical.

## Discovery rule

A session is discoverable only when `consent.share_enabled` and
`consent.share_thought_dna` are both true. Hidden or unshared Thought DNA
is never indexed. Coarse location is returned only when
`share_coarse_location` is true.

`demo.corpus.discovery.discover` indexes discoverable graphs through
`ResonanceEngine` and joins presentation metadata afterwards. Changing
topic/location/display labels cannot change ranking.

## Seeded clusters

- `accumulating-intermediary-failure` — plasma-lens flagship plus
  organization, battery, traffic, and warehouse analogs; plus partial,
  granularity, rewire, polarity, and a hidden irrigation analog.
- `method-resource-hub` — observability / clinical diagnostics / education.
- `evidence-corroboration` — archaeology / litigation / climate attribution.
- `complementary-bridge` — knowledge `requires`/`about` specialists.
- `unrelated-distractor` — star-topology negatives, including a "lens"
  photography vocabulary trap.

Flagship query: `ses-aria-plasma-lens`.

## What this corpus does not do

- It does not change frozen Benchmark v0.1 gold, thresholds, or engine code.
- It does not put retrieval, alignment, or scoring logic in the demo layer.
- It does not store private chat text, emails, phone numbers, or precise
  location pins. Coordinates are synthetic city centroids on a 0.1° grid.
