# Architecture Decisions

This directory contains proposed and accepted Architecture Decision Records (ADRs) for Resonance.

Research submissions do not become architecture automatically. They are inputs to review, benchmark, and decision.

## ADR sequence expected from R0

Likely first records:

```text
ADR-0001 — Thought Graph representation class
ADR-0002 — retrieval / fingerprint strategy
ADR-0003 — structural verification strategy
ADR-0004 — invariance handling / multiscale policy
ADR-0005 — Knowledge DNA interface
ADR-0006 — extraction and provenance contract
ADR-0007 — Resonance score and explanation contract
```

The numbering/order may change as evidence arrives.

## Current records

- [ADR-0002 — candidate retrieval with gated multi-scale structural fingerprints](ADR-0002-retrieval-candidate-generation.md) (engine 0.1; partially superseded)
- [ADR-0003 — typed partial graph alignment for structural verification](ADR-0003-structural-verification.md) (engine 0.1; partially superseded)
- [ADR-0004 — concept-aligned analogy, multi-skeleton benchmark, verified ranking](ADR-0004-concept-aligned-analogy-and-benchmark-v0.2.md) (engine 0.2, accepted)

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
