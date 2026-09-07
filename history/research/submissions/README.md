# Research Submissions

This directory contains raw research outputs produced in response to canonical missions.

A submission is **evidence**, not an architecture decision.

## Naming

```text
<mission>_<run>_<model-or-contributor>.md
```

Examples:

```text
R0_B1_fingerprinting_gpt56.md
R0_B2_fingerprinting_opus5.md
R0_B3_fingerprinting_grok46.md
R0_C3_alignment_alice_manual.md
```

## Provenance

Begin every report with the metadata header specified in `research/MISSION_CONTRACT.md`.

If the run was intended to be independent, explicitly note whether the contributor had seen sibling submissions before producing the result.

## Preserve raw results

Do not edit a returned report merely to make it agree with later architecture. Corrections can be committed with clear history, but disagreements and failed recommendations are useful project evidence.

Comparative analysis belongs in `research/reviews/`. Accepted decisions belong in `docs/decisions/`.