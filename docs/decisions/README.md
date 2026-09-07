# Architecture Decisions

This directory contains proposed and accepted Architecture Decision Records (ADRs) for Resonance.

Research submissions do not become architecture automatically. They are inputs to review, benchmark, and decision.

## Current records

- [ADR-0002 — candidate retrieval with gated multi-scale structural fingerprints](ADR-0002-retrieval-candidate-generation.md) (engine 0.1; partially superseded)
- [ADR-0003 — typed partial graph alignment for structural verification](ADR-0003-structural-verification.md) (engine 0.1; partially superseded)
- [ADR-0004 — concept-aligned analogy, multi-skeleton benchmark, verified ranking](ADR-0004-concept-aligned-analogy-and-benchmark-v0.2.md) (engine 0.2, accepted)
- [ADR-0005 — same-vocabulary cross-domain pairs: `approximate` vs `analogical`](ADR-0005-same-vocabulary-cross-domain-verdict.md) (**proposed / open**; needs human-authored gold)
- [ADR-0006 — a local label encoder beside the lexicon](ADR-0006-label-encoder.md) (accepted 2026-09-06; opt-in, on in the hosted deployment)
- [ADR-0007 — same-subject resonance, and ranking on meaning as well as shape](ADR-0007-same-subject-resonance-and-ranking.md) (accepted 2026-09-06; from the first real pair of real thoughts)

## Numbering, and the record that was never written

R0 planned a different sequence from the one that happened. It is kept here
because the divergence is itself part of the trail, not because it is a
to-do list:

```text
planned                                     actual
ADR-0001 Thought Graph representation       never written -- see below
ADR-0002 retrieval / fingerprint            ADR-0002 (as planned)
ADR-0003 structural verification            ADR-0003 (as planned)
ADR-0004 invariance / multiscale policy     ADR-0004 concept-aligned analogy
ADR-0005 Knowledge DNA interface            ADR-0005 same-vocabulary verdict
ADR-0006 extraction / provenance contract   ADR-0006 local label encoder
ADR-0007 score / explanation contract       folded into ADR-0003 + src/scoring
```

**ADR-0001 does not exist.** The representation decision it would have
recorded was taken and is specified in
[`docs/THOUGHT_DNA_v0.1.md`](../THOUGHT_DNA_v0.1.md), with the invariance
requirements that drove it in
[`docs/INVARIANCE_SPECIFICATION_v0.1.md`](../INVARIANCE_SPECIFICATION_v0.1.md)
and the rejected alternatives in [`WHY_NOT.md`](../../WHY_NOT.md). What is
missing is not the reasoning but its ADR-shaped summary — the one decision in
the chain a reader cannot find by opening this directory. Writing it is
outstanding work, and until it is written this paragraph is the pointer.

## Required ADR content

Each ADR should contain:

```markdown
# Title

Status: proposed | accepted | superseded | rejected
Date: YYYY-MM-DD

## Context
## Decision
## Evidence
## Alternatives Considered
## Consequences
## Benchmark / Validation
## Known Failure Modes
## Conditions for Reconsideration
## Related Research
```

## Rule

A decision should be specific enough that an implementation agent can build it without having to reinterpret the entire research archive.

When an ADR is superseded, keep the old record and link to the replacement. The history of changed decisions is part of the project.
