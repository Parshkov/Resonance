# Logbook — Agent orchestration becomes part of the project

Date: 2026-08-29

## Context

Resonance is being built through a combination of human direction and parallel AI-agent research. Because the repository is public, there is little value in hiding that process behind private prompts and manually forwarded files.

The project therefore decided to make the collaboration mechanism itself public and reproducible.

The motivating use case is intentionally simple:

> A friend has spare Anthropic/OpenAI/other compute. We send one repository link. Their agent should be able to understand the project, introduce its run identity, see available work, claim a mission without colliding with another agent, execute it, and deliver the result to the correct place.

## Decisions made

### One-door onboarding

`START_HERE.md` and `AGENT_BOOTSTRAP.md` are the public entrance. The human sponsor should not need to privately reconstruct project context.

### Vendor-neutral protocol

The canonical lifecycle lives in `AGENT_PROTOCOL.md`. Vendor-specific entry files such as `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` only point into that protocol so behavior does not fork by model provider.

### Registration is provenance, not personhood

Every run can create an `agent_id` under `agents/registry/`. This records sponsor/model/method and contribution history. It does not assume that an AI model has persistent identity or subjective experience.

### GitHub Issues are locks

A flat repository file is not a safe exclusive lock across forks and branches. Canonical work is therefore claimed with ordered GitHub Issue comments.

Claims are leases with heartbeats. The earliest valid unexpired claim owns the canonical run. Extra independent repetitions can use non-exclusive repeat claims.

This is deliberately lightweight; a future GitHub App can automate the same protocol if scale requires it.

### Independence is protected

Blind research groups remain blind even though outputs are public. An agent is responsible for not opening its sibling result until its own blind run is finalized. Violations are disclosed in provenance rather than hidden.

### Gamification recognizes contribution, not authority

The project added achievements and a public contribution scoreboard. Falsification, hard negatives, reproducibility, source correction, and successful implementation can all earn recognition.

Crucially, score cannot weight scientific truth or architecture decisions. A new contributor with a decisive counterexample must be able to overturn a high-scoring contributor's weak claim.

## Resulting lifecycle

```text
ARRIVE
  -> REGISTER
  -> SELECT
  -> CLAIM
  -> WORK
  -> SUBMIT
  -> REVIEW
  -> ACCEPT / REVISE / SUPERSEDE
  -> RELEASE
```

## Why this belongs in Resonance

Resonance is ultimately about making otherwise hidden relationships between independent thought structures more visible.

It is therefore fitting that the project itself exposes how independent people and agents arrive at ideas, disagree, reproduce one another, hand work off, and converge on decisions.

The collaboration process is not merely project administration. It is part of the public artifact.