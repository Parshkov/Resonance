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
├── ROADMAP.md                execution roadmap through MCP acceptance
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
│   ├── queue.yaml            complete machine-readable mission/dependency map
│   ├── STATE_MACHINE.md      prerequisite + canonical mission-slot states
│   └── CLAIM_PROTOCOL.md     claims, leases, submit, review, reopen
│
├── research/
│   ├── README.md
│   ├── R0_MASTER_BRIEF.md
│   ├── R0_EXECUTION_PLAN.md
│   ├── MISSION_CONTRACT.md
│   ├── missions/             R0 model-independent research tasks
│   ├── submissions/          raw human/agent research results
│   ├── reviews/              comparative/adversarial synthesis
│   └── logbook/              chronological research/engineering record
│
├── engineering/
│   ├── README.md             R1–R6 implementation chain
│   ├── MISSION_CONTRACT.md   engineering evidence/acceptance contract
│   └── missions/             schema → engine → MCP mission contracts
│
├── docs/
│   ├── ARCHITECTURE_LOOP.md
│   ├── STATUS.md
│   └── decisions/            accepted ADRs
│
├── benchmark/                frozen falsification/regression fixtures
├── demo/
│   ├── corpus/               the accepted R7 demo corpus
│   └── ui/                   the page: screens, state store, browser tools
├── ops/                      deployment, migrations, acceptance probes
├── schemas/                  published JSON Schemas
├── brand/                    logo assets
├── archive/hackathon/        the WebMCP Challenge build record and its evidence
└── src/                      the engine, and the product built on it
```

## Artifact lifecycle

```text
Research Mission
  -> Submission
  -> Review
  -> Decision / ADR
  -> Executable schema/interfaces/benchmark
  -> Component implementation
  -> Integrated engine gate
  -> MCP adapter
  -> clean-client E2E acceptance
```

Every step can produce new evidence that causes an earlier decision to be revised. Nothing is accepted merely because it is generated or merged.

## Work-state lifecycle

Canonical work ownership and artifact existence are separate concepts.

A mission with unaccepted prerequisites begins as:

```text
BLOCKED
  -> AVAILABLE                  all prerequisites ACCEPTED
  -> CLAIMED / WORKING
  -> SUBMITTED / PENDING_REVIEW
  -> ACCEPTED / REVISION_REQUESTED / REJECTED / SUPERSEDED
```

Abandoning before submission returns the slot to `AVAILABLE` only when prerequisites remain accepted; otherwise it returns to `BLOCKED`. Submission does not release the canonical slot and does not satisfy downstream prerequisites.

A fresh canonical run after submission/review requires `REOPEN_CANONICAL`. Independent repeats remain available according to mission policy.

See `work/STATE_MACHINE.md` and `work/CLAIM_PROTOCOL.md`.

## What belongs where

### `research/missions/`

R0 research question and acceptance contract. Missions should be vendor-independent. Do not store a model answer here.

### `research/submissions/`

Raw returned research. Preserve disagreements and failed proposals. Add provenance metadata.

### `research/reviews/`

Comparison across research submissions. A review should resolve, or make experimentally resolvable, the differences between reports.

### `docs/decisions/`

Actual architecture decisions. A model recommendation is not an ADR until the project accepts it.

### `engineering/missions/`

Durable scope, ownership surface, prerequisites and acceptance gates for R1–R6 implementation. GitHub Issues remain the live coordination stream.

### `engineering/MISSION_CONTRACT.md`

The evidence and submission rules for implementation missions. It requires executable code/tests where implementation is requested, frozen benchmark discipline, accepted prerequisites, and a strict core/MCP boundary.

### `research/logbook/`

Chronological context: why a question appeared, what changed, which hypothesis was abandoned, and what happened between formal artifacts.

### `benchmark/`

Executable or inspectable cases designed to falsify claims. Gate fixtures are versioned/frozen and may not be rewritten to make a current engine pass.

### `src/`

Implementation after the relevant gates, in two layers.

**The engine** — protocol-free and product-free. R2 extraction, R3 retrieval
and R4 verification communicate through accepted R1 interfaces; R5 integrates
them behind one facade.

```text
graph/        Thought DNA model, validation, canonical hashing
semantics/    lexicon, stemmer, similarity, optional local label encoder
extraction/   prose -> Thought Graph (cue extractor, no LLM)
fingerprint/  structural and concept keys
index/        inverted multi-channel candidate index
alignment/    FGW / RRWM structural verification
scoring/      component formulas, classification policy, confidence
interfaces/   the frozen boundaries the above talk through
engine/       the composed facade
```

**The product** — everything that turns the engine into something people use.
It depends on the engine; the engine never depends on it.

```text
discovery/     consented, visualization-ready read model over engine results
ingestion/     private prepare -> preview -> explicit share
identity/      accounts, sessions, consent, federation, pseudonyms
persistence/   SQLite and PostgreSQL repositories, migrations, projection
security/      fail-closed authorization kernel, audit, rate limits
collaboration/ intro state machine and private relay
workspaces/    multi-person workspaces and shared topics
product/       the HTTP server, the MCP tool vocabulary, presentation
remote/        OAuth 2.1 core and the remote MCP entry point
```

There is **no** `src/mcp/`. The classic stdio adapter and the second remote
server with its own divergent tool vocabulary were both retired; one
vocabulary of `resonance_*` tools now lives in `src/product/mcp_bridge.py`
and is served to the browser and to chat clients alike.

### `work/queue.yaml`

The complete machine-readable mission/dependency map. It is not an exclusive lock and does not by itself prove that a mission is available; prerequisites and issue state must be resolved first.

### `work/STATE_MACHINE.md`

The canonical definition of prerequisite blocking, mission-slot states and transitions.

### `work/CLAIM_PROTOCOL.md`

The exact GitHub Issue event formats used to claim, renew, submit, abandon, review, and explicitly reopen canonical work.

## GitHub Issues

Issues are the public orchestration layer: ownership, model run, status, blockers, review outcomes and discussion.

The durable result should still be committed to the appropriate research, engineering, benchmark, docs or source path. An issue comment alone is not the durable scientific/engineering record.

When determining canonical work availability, first resolve queue prerequisites, then read the issue event history under `work/STATE_MACHINE.md`; do not infer availability from the absence of recent compute activity or from a merged PR.

## Contributor rule of thumb

If you are unsure where something belongs:

- a **research question** becomes a research Mission;
- a **research answer** becomes a Submission;
- a **comparison** becomes a Review;
- an **architecture choice** becomes an ADR;
- a **counterexample** becomes Benchmark data;
- an **engineering task** becomes an engineering Mission + linked Issue;
- an **implementation** goes in its mission-owned `src/`/test/fixture surface;
- an **integration result** belongs to R5 evidence and tests;
- an **MCP transport change** belongs under the R6 mission and must wrap the engine;
- a **historical explanation** goes in the Logbook or `WHY_NOT.md`;
- a **work-state event** goes on the mission Issue according to `work/CLAIM_PROTOCOL.md`.