# R7-CORPUS — Consented multi-session demo corpus

Issue: #72

## Objective
Create a small, deterministic, consent-aware multi-person/session corpus that lets the accepted Resonance engine demonstrate human-to-human structural resonance discovery, not merely pairwise benchmark comparison.

This is demo infrastructure, not a production social graph and not a claim of population-scale performance.

## Prerequisites
- R6-MCP (#44) ACCEPTED (hard start gate).
- R6-E2E (#45) should be accepted before final integration. Corpus preparation may proceed in parallel because this mission must not modify engine/retrieval/scoring semantics.

## Ownership
`demo/corpus/**`, `schemas/demo-corpus-0.1.schema.json`, corpus validator/build/discovery helpers, and `tests/test_demo_corpus.py`. Do not change accepted R2/R3/R4/R5/R6 matching semantics, frozen gold, or thresholds.

## Required corpus shape
20–50 seeded sessions with:

- at least three cross-domain resonance clusters;
- near matches and meaningful partial matches;
- same-words/wrong-structure negatives;
- polarity/causal inversion negatives;
- unrelated distractors;
- at least one query with 2–4 useful consented matches;
- stable IDs and presentation metadata that MUST NOT become matching features;
- consent/share state and coarse/synthetic location only;
- provenance: synthetic, volunteer-provided, or manually curated.

## Acceptance
Use issue #72. Deterministic rebuild/load; consent-disabled records impossible to discover through the demo discovery path; presentation metadata cannot silently alter resonance ranking; full existing test suite remains green.
