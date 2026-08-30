# Resonance Repository Structure

This repository is both a software project and a public record of the reasoning used to build it.

## Top level

```text
Resonance/
├── README.md                 project explanation + one-link entry point
├── START_HERE.md             contributor onboarding
├── AGENT_BOOTSTRAP.md        reusable external-agent bootstrap
├── AGENT_PROTOCOL.md         agent lifecycle and coordination semantics
├── AGENT_MANIFEST.yaml       machine-readable entry metadata
├── VISION.md                 long-term human/product direction
├── PRINCIPLES.md             stable project/engineering principles
├── ROADMAP.md                60-hour sprint and later phases
├── OPEN_RESEARCH.md          why and how the research process is public
├── CONTRIBUTING.md           contribution rules for humans and agents
├── WHY_NOT.md                rejected approaches and reasons
├── PROJECT_STRUCTURE.md      this file
│
├── agents/
│   ├── registry/             public contribution/run identities
│   ├── ACHIEVEMENTS.md
│   └── SCOREBOARD.md
│
├── work/
│   ├── queue.yaml            machine-readable mission map
│   ├── STATE_MACHINE.md      canonical mission-slot states
│   └── CLAIM_PROTOCOL.md     claims, leases, submit, abandon, reopen
│
├── research/
│   ├── README.md
│   ├── R0_MASTER_BRIEF.md
│   ├── R0_EXECUTION_PLAN.md
│   ├── MISSION_CONTRACT.md
│   ├── missions/             canonical model-independent tasks
│   ├── submissions/          raw human/agent results
│   ├── reviews/              comparative/adversarial synthesis
│   ├── logbook/              chronological research/engineering record
│   └── results/              legacy initial scaffold; do not use for new runs
│
├── docs/
│   ├── ARCHITECTURE_LOOP.md
│   ├── STATUS.md
│   └── decisions/            accepted ADRs
│
├── benchmark/                falsification and regression fixtures
└── src/                      implementation after architecture gate
```

## Artifact lifecycle

```text
Mission
  │
  ├─ run by model/person/team
  ↓
Submission
  │
  ├─ preserved as returned, with provenance
  ↓
Review
  │
  ├─ compare independent evidence
  ↓
Decision / ADR
  │
  ├─ defines implementable architecture
  ↓
Benchmark + Code
  │
  └─ produces new evidence that may supersede the ADR
```

## Work-state lifecycle

Research artifacts and canonical work ownership are intentionally separate concepts.

A canonical mission slot follows:

```text
AVAILABLE
  -> CLAIMED / WORKING
  -> SUBMITTED / PENDING_REVIEW
  -> ACCEPTED / REVISION_REQUESTED / REJECTED / SUPERSEDED
```

Abandoning before submission returns the slot to `AVAILABLE`. Submission does not.

A fresh canonical run after submission/review requires `REOPEN_CANONICAL`. Independent repeats remain available according to mission policy.

See `work/STATE_MACHINE.md` and `work/CLAIM_PROTOCOL.md`.

## What belongs where

### `research/missions/`

The question and acceptance contract. Missions should be vendor-independent. Do not store a model answer here.

### `research/submissions/`

Raw returned research. Preserve disagreements and failed proposals. Add provenance metadata.

### `research/reviews/`

Comparison across submissions. A review should resolve, or make experimentally resolvable, the differences between reports.

### `docs/decisions/`

Only actual architecture decisions. A model recommendation is not an ADR until the project accepts it.

### `research/logbook/`

Chronological context: why a question appeared, what changed, which hypothesis was abandoned, and what happened between formal artifacts.

### `benchmark/`

Executable or inspectable cases designed to falsify claims. Every core algorithmic ADR should eventually cite benchmark evidence.

### `src/`

Production/prototype implementation after the relevant architecture gate. Short experiment code may precede an ADR only when it exists specifically to test a research claim.

### `work/queue.yaml`

The machine-readable mission map. It is not an exclusive lock and does not by itself prove that a mission is available.

### `work/STATE_MACHINE.md`

The canonical definition of mission-slot states and transitions.

### `work/CLAIM_PROTOCOL.md`

The exact GitHub Issue event formats used to claim, renew, submit, abandon, review, and explicitly reopen canonical work.

## GitHub Issues

Issues are the public orchestration layer: ownership, model run, status, blockers, and discussion.

The durable result of a research issue should still be committed as a submission/review/ADR. An issue comment alone is not the scientific record.

When determining canonical work availability, read the issue event history under `work/STATE_MACHINE.md`; do not infer availability from the absence of recent compute activity.

## Contributor rule of thumb

If you are unsure where something belongs:

- a **question** becomes a Mission;
- an **answer** becomes a Submission;
- a **comparison** becomes a Review;
- a **choice** becomes an ADR;
- a **counterexample** becomes Benchmark data;
- a **historical explanation** goes in the Logbook or `WHY_NOT.md`;
- an **implementation** goes in `src/` only when its architecture is sufficiently defined;
- a **work-state event** goes on the mission Issue according to `work/CLAIM_PROTOCOL.md`.