# Resonance Repository Structure

This repository is both a software project and a public record of the reasoning used to build it.

It is also designed as a lightweight operating environment for human + AI collaboration: an agent can arrive, learn the project, register, select work, claim it, deliver a submission, and hand it off without requiring private onboarding.

## Top level

```text
Resonance/
├── README.md                 project explanation
├── START_HERE.md             one-door onboarding for humans and agents
├── AGENT_BOOTSTRAP.md        copy-paste prompt for an external agent
├── AGENT_PROTOCOL.md         canonical agent lifecycle / coordination rules
├── AGENT_MANIFEST.yaml       machine-readable project entry points
├── AGENTS.md                 repository-native generic/Codex agent adapter
├── CLAUDE.md                 Claude adapter -> canonical protocol
├── GEMINI.md                 Gemini adapter -> canonical protocol
│
├── VISION.md                 long-term human/product direction
├── PRINCIPLES.md             stable project/engineering principles
├── ROADMAP.md                60-hour sprint and later phases
├── OPEN_RESEARCH.md          why and how the research process is public
├── CONTRIBUTING.md           contribution rules for humans and agents
├── WHY_NOT.md                rejected approaches and reasons
├── PROJECT_STRUCTURE.md      this file
│
├── agents/
│   ├── README.md
│   ├── registry/             public run identities and provenance
│   ├── ACHIEVEMENTS.md       contribution achievements / scoring rules
│   └── SCOREBOARD.md         public accepted contribution history
│
├── work/
│   ├── README.md
│   ├── queue.yaml            machine-readable mission map
│   └── CLAIM_PROTOCOL.md     lock lease / heartbeat / race rules
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
├── src/                      implementation after architecture gate
└── .github/
    └── PULL_REQUEST_TEMPLATE.md
```

## Contributor / agent lifecycle

```text
START_HERE
   ↓
Agent registration
   ↓
work/queue.yaml
   ↓
GitHub Issue CLAIM lease
   ↓
Mission execution
   ↓
Submission + PR
   ↓
Review
   ↓
Decision / benchmark / code
   ↓
Achievement + public contribution trail
```

GitHub Issues are the **live coordination layer**. Repository files are the durable scientific/engineering record.

A flat file is intentionally not used as an exclusive lock: issue comments provide a globally ordered public sequence of claims, heartbeats, releases, and blockers.

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

## What belongs where

### `agents/registry/`

Public provenance for a participating run identity: sponsor, model/method, environment, and links to contributions. Never store credentials.

### `work/queue.yaml`

The machine-readable map from run id to mission file, GitHub issue, output path, blind group, and claim behavior. Issue state remains live source of truth.

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

## GitHub Issues

Issues are the public orchestration layer: claims, leases, ownership of canonical runs, model run, status, blockers, and discussion.

The durable result of a research issue should still be committed as a submission/review/ADR. An issue comment alone is not the scientific record.

## Conflict avoidance

- canonical runs are claimed through ordered Issue comments;
- claims expire unless renewed;
- independent repeats use unique run ids and never overwrite canonical output;
- blind siblings must not inspect each other before submission;
- agents normally write only their own registry profile + submission in a research PR;
- shared coordination documents are maintained separately from active mission work.

## Contributor rule of thumb

If you are unsure where something belongs:

- an **identity/provenance record** goes under `agents/registry/`;
- a **work claim** goes on the mission Issue;
- a **question** becomes a Mission;
- an **answer** becomes a Submission;
- a **comparison** becomes a Review;
- a **choice** becomes an ADR;
- a **counterexample** becomes Benchmark data;
- a **historical explanation** goes in the Logbook or `WHY_NOT.md`;
- an **implementation** goes in `src/` only when its architecture is sufficiently defined.

If you arrived with an agent and do not know where to begin, open `START_HERE.md`.