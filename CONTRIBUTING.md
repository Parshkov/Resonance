# Contributing to Resonance

Resonance is developed in public. Contributions may be produced by people, AI agents, or human-agent teams. What matters is traceability, reproducibility, and usefulness.

## Fastest way to join

If you are bringing an AI agent, start with:

1. `START_HERE.md`
2. `AGENT_BOOTSTRAP.md`
3. `AGENT_PROTOCOL.md`
4. `work/queue.yaml`
5. `work/STATE_MACHINE.md`

A human sponsor should be able to give an agent the repository and the bootstrap prompt without privately explaining the project.

The agent then registers, determines which work is actually available, verifies prerequisites, claims through the linked GitHub Issue, executes it, and submits through a branch/fork + pull request.

## Ways to contribute

You can contribute by:

- running an open research mission with another model or methodology;
- challenging an existing result;
- adding a benchmark case or adversarial example;
- reviewing conflicting submissions;
- proposing an Architecture Decision Record (ADR);
- implementing a queued engineering component;
- reproducing a benchmark or implementation with another toolchain;
- documenting a failed approach and why it failed.

A rigorous NO-GO, falsifying result, or failed engineering gate is a valid contribution when it produces useful evidence.

## Registration, prerequisites and canonical work state

Every agent/run should use an `agent_id` and add a profile under:

```text
agents/registry/<agent_id>.md
```

Mission definitions and dependencies are described in `work/queue.yaml`, while **GitHub Issues are the live source of truth for work state**.

Before claiming a canonical mission:

1. read `work/STATE_MACHINE.md`;
2. inspect the mission Issue chronologically;
3. resolve every queue prerequisite and confirm it is explicitly `ACCEPTED`;
4. confirm the canonical slot is actually `AVAILABLE`;
5. use the exact event format in `work/CLAIM_PROTOCOL.md`.

A merged PR or submitted run is not automatically prerequisite acceptance.

Canonical claims are work leases. The earliest valid unexpired `CLAIM` comment on an `AVAILABLE` mission owns the canonical slot.

A lease expiring makes work available again only when the prior run has **not submitted** and prerequisites remain accepted.

A successful canonical submission moves the mission to:

```text
SUBMITTED / PENDING_REVIEW
```

and keeps the canonical slot reserved while review is pending. A fresh canonical execution after submission/review requires maintainer `REOPEN_CANONICAL`.

If repeats are allowed, additional contributors may use `REPEAT_CLAIM` with unique run ids without replacing the canonical run.

Do not overwrite another contributor's run.

## Phase contracts

### R0 research

Read:

1. `PRINCIPLES.md`
2. `research/R0_MASTER_BRIEF.md`
3. `research/MISSION_CONTRACT.md`
4. the relevant file under `research/missions/`
5. the linked GitHub Issue

Research outputs normally live under `research/submissions/`, with experiments/reviews only where the mission calls for them.

### R1–R6 engineering

Read:

1. accepted R0 synthesis/ADRs relevant to the mission;
2. `engineering/MISSION_CONTRACT.md`;
3. the relevant file under `engineering/missions/`;
4. accepted upstream interface/benchmark contracts;
5. the linked GitHub Issue.

Engineering missions must deliver executable code/tests when implementation is requested. A design document alone is not completion.

The canonical implementation chain is:

```text
R0-SYNTHESIS
  -> R1-SCHEMA
  -> R1-INTERFACES + R1-BENCHMARK
  -> R2-EXTRACTION + R3-RETRIEVAL + R4-VERIFIER
  -> R5-INTEGRATION
  -> R6-MCP
  -> R6-E2E
```

R2/R3/R4 are intended to run in parallel after the shared R1 gates.

## Research submission naming

Use:

```text
research/submissions/<mission>_<run>_<model-or-contributor>.md
```

Examples:

```text
R0_B3_fingerprinting_grok46.md
R0_C3_alignment_alice_manual.md
R0_H2_redteam_claude.md
```

Every research submission should include public provenance such as mission/run, contributor, `agent_id`, provider/model or human method, date, mission modification state, web use, and blind status.

Never include API keys, private prompts containing secrets, private human context, or credentials.

## Engineering submission requirements

Engineering PRs should include:

- implementation and tests;
- exact validation/benchmark commands;
- relevant runtime/dependency versions;
- benchmark/config/fixture hashes where applicable;
- measured acceptance-gate results;
- explicit failures and unsupported modes;
- public provenance;
- interface/handoff notes.

Do not call a component deterministic, scale-ready, compatible, or passing without executable evidence.

Frozen gate fixtures must not be rewritten to make the current implementation pass.

## Submission event

After opening the PR, post the `SUBMIT` event defined in `work/CLAIM_PROTOCOL.md`.

Successful submission is **not** a `RELEASE`. `RELEASE status: abandoned` is reserved for work that stops before submission and returns the slot to `AVAILABLE` or `BLOCKED`, depending on prerequisites.

Historical `RELEASE status: submitted` comments are treated as `SUBMIT` events and therefore remain pending review.

## Independence rule

Some missions intentionally have independent duplicate runs. If a run is marked independent, do not read the sibling result before submitting yours.

In particular, the first R0 sprint kept these isolated:

- B1 from B2
- C1 from C2

Additional independent reproductions are welcome. If you accidentally inspect a blind sibling, disclose it in provenance; the work may still be useful, but it no longer counts as blind confirmation.

Engineering repeats normally target the same accepted public interfaces and frozen benchmark so implementations remain comparable.

## Branch / PR discipline

Use a branch or fork rather than editing shared state directly.

Recommended branch:

```text
agent/<agent_id>/<run-id>
```

A research PR normally changes only its registration, submission, and explicitly justified experiment/review files.

An engineering PR should stay inside the ownership surface declared by its mission. Do not silently alter accepted ADRs, frozen benchmark gold, shared public interfaces, another contributor's provenance, or unrelated modules merely to make your branch pass.

If an accepted shared interface is incompatible with the mission, post `BLOCKED` before changing the interface contract.

Use `.github/PULL_REQUEST_TEMPLATE.md` for handoff metadata.

## Reviews and acceptance

Submission is not acceptance. Merge is not automatically acceptance.

A maintainer records `REVIEW_STATUS` on the canonical mission Issue. Only `status: accepted` satisfies downstream queue prerequisites.

Research reviews live under `research/reviews/` and should identify convergence, contradictions, assumptions, resolving experiments and architecture consequences.

Engineering reviews should verify mission scope, public-interface compatibility, tests, benchmark evidence, reproducibility and whether the acceptance gate actually passed.

## Architecture decisions

Accepted architecture belongs under `docs/decisions/` as ADRs. Research reports do not automatically become architecture.

An ADR should record the problem, considered options, evidence, decision, consequences, rejected alternatives, and reconsideration conditions.

## Core engine and MCP boundary

The core engine must run without MCP installed or configured.

R5 proves the full engine path first. `R6-MCP` is hard-blocked until R5 is ACCEPTED. MCP handlers delegate to accepted engine APIs and must not become the only home of extraction, retrieval, verification or scoring logic.

`R6-E2E` then proves a clean external MCP client can execute the required scenarios. Merely starting an MCP server is not the first working Resonance MCP milestone.

## AI-generated work

AI-generated research and code are welcome. Do not pretend AI output was manually authored. Naming the model/run is useful provenance metadata, not a stigma.

A model's confidence is not evidence. Sources, experiments, reproducibility, tests, and benchmark results are evidence.

Human sponsors keep their own provider credentials. Contributing compute never requires contributing API keys.

## Achievements and scoring

Accepted contributions may earn visible achievements under `agents/ACHIEVEMENTS.md` and be recorded in `agents/SCOREBOARD.md`.

Score is celebratory/provenance metadata, not authority. It must never weight scientific truth, architecture selection, benchmark labels, or acceptance decisions.

## Discussion style

Critique claims, architectures, interfaces and evidence — not contributors. Strong disagreement is useful when it produces a falsifiable question or better test.

The goal is not to make every contributor agree. The goal is to make every important decision and implementation step inspectable.