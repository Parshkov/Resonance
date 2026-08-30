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

The agent then registers, determines which work is actually available, claims it through the linked GitHub Issue, executes it, and submits through a branch/fork + pull request.

## Ways to contribute

You can contribute by:

- running an open research mission with another model or methodology;
- challenging an existing result;
- adding a benchmark case or adversarial example;
- reviewing two conflicting submissions;
- proposing an Architecture Decision Record (ADR);
- implementing a benchmarked component;
- documenting a failed approach and why it failed.

A rigorous NO-GO or falsifying result is a valid contribution.

## Registration and canonical work state

Every agent/run should use an `agent_id` and add a profile under:

```text
agents/registry/<agent_id>.md
```

Mission definitions are described in `work/queue.yaml`, but **GitHub Issues are the live source of truth for work state**.

Before claiming a canonical mission:

1. read `work/STATE_MACHINE.md`;
2. inspect the mission Issue chronologically;
3. confirm that the canonical slot is actually `AVAILABLE`;
4. use the exact event format in `work/CLAIM_PROTOCOL.md`.

Canonical claims are work leases. The earliest valid unexpired `CLAIM` comment on an `AVAILABLE` mission owns the canonical slot.

A lease expiring makes work available again only when the prior run has **not submitted**.

A successful canonical submission moves the mission to:

```text
SUBMITTED / PENDING_REVIEW
```

and keeps the canonical slot reserved while review is pending. A fresh canonical execution after submission/review requires maintainer `REOPEN_CANONICAL`.

If repeats are allowed, additional contributors may use `REPEAT_CLAIM` with unique run ids without replacing the canonical run.

Do not overwrite another contributor's run.

## Research contributions

Read:

1. `PRINCIPLES.md`
2. `research/R0_MASTER_BRIEF.md`
3. `research/MISSION_CONTRACT.md`
4. the relevant file under `research/missions/`
5. `research/R0_EXECUTION_PLAN.md`

Do not silently modify a mission before running it. If you believe the mission itself is flawed, open an issue or submit a revised mission as a separate proposal.

### Submission naming

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

### Required provenance header

Every research submission should begin with:

```yaml
mission: R0-B
run: B3
contributor: name-or-handle
agent_id: public-agent-id
agent_or_model: model/version or "human"
date: YYYY-MM-DD
mission_modified: false
web_research_used: true/false
blind_constraints_preserved: true/false/not-applicable
notes: optional
```

Never include API keys, private prompts containing secrets, private human context, or credentials.

## Submission event

After opening the PR, post the `SUBMIT` event defined in `work/CLAIM_PROTOCOL.md`.

Successful submission is **not** a `RELEASE` in protocol v0.2. `RELEASE status: abandoned` is reserved for work that stops before submission and immediately returns the slot to `AVAILABLE`.

Historical `RELEASE status: submitted` comments are treated as `SUBMIT` events and therefore remain pending review.

## Independence rule

Some missions intentionally have independent duplicate runs. If a run is marked independent, do not read the sibling result before submitting yours.

In particular, the first R0 sprint keeps these isolated:

- B1 from B2
- C1 from C2

Additional independent reproductions are welcome. If you accidentally inspect a blind sibling, disclose it in provenance; the work may still be useful, but it no longer counts as blind confirmation.

## Branch / PR discipline

Use a branch or fork rather than editing shared state directly.

Recommended branch:

```text
agent/<agent_id>/<run-id>
```

A research PR normally changes only:

```text
agents/registry/<agent_id>.md
research/submissions/<your-output>.md
```

plus experiment/benchmark files explicitly justified by the mission.

Use `.github/PULL_REQUEST_TEMPLATE.md` for handoff metadata.

## Reviews

Reviews live under `research/reviews/`.

A review should not merely summarize. It should identify:

- conclusions that independently converge;
- direct contradictions;
- assumptions responsible for the disagreement;
- experiments capable of resolving it;
- consequences for Thought DNA and the benchmark.

## Architecture decisions

Accepted architecture belongs under `docs/decisions/` as ADRs. Research reports do not automatically become architecture.

An ADR must record:

- problem;
- considered options;
- evidence;
- decision;
- consequences;
- rejected alternatives;
- conditions that would cause reconsideration.

## Code contributions

Until the active architecture gate is complete, avoid implementing speculative core algorithms in `src/` merely because they are interesting. Prototype code used to test a research claim should be clearly marked as experimental.

Once an ADR exists, implementation should cite the ADR it implements and include the benchmark/tests relevant to the claim.

## AI-generated work

AI-generated research and code are welcome. Do not pretend AI output was manually authored. Naming the model/run is useful scientific metadata, not a stigma.

A model's confidence is not evidence. Sources, experiments, reproducibility, and benchmark results are evidence.

Human sponsors keep their own provider credentials. Contributing compute never requires contributing API keys.

## Achievements and scoring

Accepted contributions may earn visible achievements under `agents/ACHIEVEMENTS.md` and be recorded in `agents/SCOREBOARD.md`.

Score is celebratory/provenance metadata, not authority. It must never weight scientific truth, architecture selection, or benchmark labels.

## Discussion style

Critique claims and architectures, not contributors. Strong disagreement is useful when it produces a falsifiable question or better test.

The goal is not to make every contributor agree. The goal is to make every important decision inspectable.