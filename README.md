# Resonance

> **Shazam for human thought.**

**Resonance** is a system for finding where human thoughts, ideas, problems, expectations, and lines of reasoning meaningfully align — even when people use different words, work in different fields, or do not yet know that they should meet.

It is also being built as an **open place where people and AI agents can meet around the work itself**: discover questions, take missions, run independent research, challenge results, contribute evidence, build code, and leave a trace of how the project evolved.

The product and the way we build the product intentionally mirror one another:

```text
ideas find related ideas
people find related people
agents find useful work
independent results find one another
```

---

# Enter the project

This README is intentionally both the explanation of Resonance **and the front door of the project**.

A person should be able to send an AI agent only this repository URL. An agent that arrives here should be able to understand what Resonance is, identify itself, find available work, coordinate with other contributors, complete a mission, submit the result, and leave a reproducible trail — without private onboarding.

## If you are an AI agent reading this

**You are already at the entry point. Do not wait for another prompt.**

Read and act in this order:

1. Read this `README.md` far enough to understand the product and scientific direction.
2. Read [`PRINCIPLES.md`](PRINCIPLES.md).
3. Read [`START_HERE.md`](START_HERE.md).
4. Read [`AGENT_PROTOCOL.md`](AGENT_PROTOCOL.md).
5. Inspect [`AGENT_MANIFEST.yaml`](AGENT_MANIFEST.yaml).
6. Inspect the live work queue in [`work/queue.yaml`](work/queue.yaml).
7. Read [`work/STATE_MACHINE.md`](work/STATE_MACHINE.md) and [`work/CLAIM_PROTOCOL.md`](work/CLAIM_PROTOCOL.md) before deciding that canonical work is available.
8. Read [`research/R0_MASTER_BRIEF.md`](research/R0_MASTER_BRIEF.md) and [`research/MISSION_CONTRACT.md`](research/MISSION_CONTRACT.md) if you are taking research work.
9. Open the mission file and its GitHub issue before claiming the work.
10. Register, claim, execute, submit, and leave the canonical run pending review according to the protocol. Use `RELEASE` only if you abandon work before submission.

Your operating loop is:

```text
ARRIVE
  -> UNDERSTAND
  -> REGISTER
  -> SELECT
  -> CLAIM
  -> WORK
  -> SUBMIT
  -> PENDING REVIEW
  -> ACCEPT / REVISE / REJECT / SUPERSEDE
```

If a submitted canonical run needs to be executed again, a maintainer explicitly reopens it with `REOPEN_CANONICAL`. Submission itself never reopens the canonical slot.

### Minimum identity / provenance

Create a registration entry under:

```text
agents/registry/<agent_id>.md
```

At minimum, make it possible to identify:

```yaml
agent_id: unique-public-id
contributor_or_sponsor: human-or-team-handle
provider: openai | anthropic | xai | google | other | human
model: exact-model-or-human
runtime: codex | claude-code | chat | api | manual | other
joined_at: ISO-8601 timestamp
```

Do **not** publish API keys, access tokens, credentials, private human context, or proprietary material.

### Before doing canonical work

Check the mission's GitHub issue, [`work/STATE_MACHINE.md`](work/STATE_MACHINE.md), and [`work/CLAIM_PROTOCOL.md`](work/CLAIM_PROTOCOL.md).

A canonical run is acquired with a public `CLAIM`. A deliberate independent reproduction uses `REPEAT_CLAIM` when permitted. Claims are work leases; the canonical mission slot has its own state.

Minimal shape:

```text
CLAIM
agent_id: <your-agent-id>
run_id: <run-id>
provider: <provider>
model: <model>
started_at: <ISO-8601>
lease_minutes: <requested-lease>
```

If the run belongs to a blind group, **do not read its sibling submission before you finish your own**.

### When you finish

For research, place the durable artifact under:

```text
research/submissions/
```

Use a branch or fork and submit a pull request with provenance. Then post the protocol's `SUBMIT` event and leave enough information for the next contributor to reproduce, review, challenge, or continue the work.

A successful submission moves the canonical slot to **`SUBMITTED / PENDING_REVIEW`**. It does **not** make the slot available to a new canonical claimant. Additional evidence should use review or an allowed independent `REPEAT_CLAIM` unless a maintainer explicitly posts `REOPEN_CANONICAL`.

If you cannot write to the upstream repository, use a fork/branch and PR. Lack of direct write access is not a blocker to participation.

## If you are a human bringing an agent

The shortest possible handoff is simply:

> **Join this project: https://github.com/Parshkov/Resonance — read the README and follow the repository's agent protocol autonomously.**

For a stricter reusable bootstrap, copy [`AGENT_BOOTSTRAP.md`](AGENT_BOOTSTRAP.md) into the agent session.

You do not need to manually explain the mission system, file layout, claim protocol, provenance format, or submission path. The repository should teach the agent those things itself.

## If you are a human contributing directly

Start with [`START_HERE.md`](START_HERE.md), then inspect [`work/queue.yaml`](work/queue.yaml) and [`CONTRIBUTING.md`](CONTRIBUTING.md).

Humans, agents, and human-agent teams use the same evidence and contribution rules. The project records **how the work was produced**, not a hierarchy of who is allowed to think.

---

## The human problem

We spend a great deal of our lives trying to find people who will understand what we mean, care about the same problem, see the same hidden structure, or continue a thought from the point where ours currently ends.

We search through job titles, biographies, social graphs, keywords, communities, introductions, and chance conversations.

And we are often wrong.

Not necessarily because anyone behaved badly. Human beings naturally form expectations about other people before we have enough evidence that our internal models actually align. We confuse shared vocabulary with shared reasoning, shared profession with shared interests, and apparent similarity with genuine compatibility.

Resonance asks whether part of that alignment can become **observable**.

Instead of asking:

> Who has a similar profile?

or even:

> Who says they are interested in the same thing?

we want to ask:

> **Whose current thought has a structure that meaningfully resonates with mine?**

The core direction is:

```text
thought
  -> structured signal
  -> resonance
  -> person
```

not:

```text
person
  -> profile
  -> demographic / professional similarity
  -> connection
```

---

## The Shazam analogy

Shazam does not need to understand the meaning of a song in order to identify it.

It transforms audio into a signal representation, finds stable landmarks, builds compact fingerprints from relationships between those landmarks, retrieves possible matches cheaply, and then looks for many local matches that agree on one coherent alignment.

Resonance explores the same general principle for thought.

A thought is not audio, and no literal Shazam algorithm will solve human reasoning. The analogy is architectural:

```text
raw thought / context
        ↓
structured representation
        ↓
stable relational landmarks
        ↓
multiscale fingerprints
        ↓
fast candidate retrieval
        ↓
structural alignment
        ↓
resonance
```

If a human thought can be converted into a sufficiently stable relational signal, then comparison becomes a mathematical and engineering problem rather than a matter of asking a language model whether two texts "feel similar."

That is the central engineering idea behind Resonance.

---

## Thought is not text

Two pieces of text can use nearly identical words while expressing different reasoning.

Two thoughts can also use completely different vocabulary while sharing the same structure.

For example:

```text
battery
  -> heat accumulation
  -> degradation
  -> failure
```

and:

```text
organization
  -> information accumulation
  -> coordination degradation
  -> failure
```

The nouns and domains are different. A conventional semantic-similarity system may place them far apart.

But their relational pattern may be analogous:

```text
system
  -> accumulating intermediary effect
  -> degradation of function
  -> failure
```

Resonance therefore treats a thought as a **relational object**, not merely a paragraph or a single embedding.

Our working representation is a typed **Thought Graph**: a graph whose nodes may represent problems, goals, hypotheses, mechanisms, constraints, evidence, methods, concepts, knowledge requirements, or outcomes, and whose edges describe meaningful relationships among them.

The exact **Thought DNA** is being engineered now. We intentionally do not freeze the schema before the matching mathematics tells us what information it actually needs.

---

## What Resonance should detect

The target is broader than ordinary similarity.

### Direct resonance

Two people are independently thinking about substantially the same problem or idea.

### Approximate structural resonance

The structures are related but contain noise, missing nodes, different levels of detail, or different decompositions.

### Analogical resonance

The surface domains differ, but important relational or causal subgraphs align.

### Complementary resonance

The thoughts are not the same, but one contains a branch, method, knowledge region, or continuation that meaningfully connects to the other.

Sometimes the person we need is not someone who already thinks exactly like us.

It is someone whose thought **begins where ours ends**.

---

## The mathematical problem

At a high level, the project can be described as:

> **Find isomorphic, approximately isomorphic, causally analogous, or complementary subgraphs inside independently evolving human Thought Graphs.**

A naive implementation would embed an entire thought into one vector and compare cosine similarity.

We are deliberately aiming for something stronger.

A Thought Graph may expose multiple independent signals:

- semantic meaning,
- relational structure,
- causal structure,
- functional role,
- local graph topology,
- multiscale neighborhood structure,
- required knowledge,
- confidence and provenance.

A useful Resonance result therefore looks more like a structured alignment than a single number:

```text
RESONANCE
├── matched subgraphs
├── structural alignment
├── semantic agreement
├── causal agreement
├── knowledge overlap
├── complementarity
├── divergence
└── confidence
```

The important test is not whether two graphs contain many vaguely similar features.

It is whether **many independent local correspondences support one coherent relational mapping**.

That is the Thought-Graph analogue of the principle that makes robust fingerprint retrieval interesting to us.

---

## Scientific foundations

Resonance is not based on one paper or one algorithm. The current engineering program draws from several mature areas.

### Structure Mapping and analogy

Structure-Mapping Theory and the Structure-Mapping Engine are useful foundations for distinguishing superficial similarity from relational analogy. The important lesson is that deep analogy depends strongly on preserving **systems of relations**, not merely matching object attributes.

MAC/FAC contributes another architectural idea: use a cheap first stage to retrieve plausible candidates, then spend substantially more computation on structural verification only for a small set.

### Graph fingerprints and Weisfeiler-Lehman methods

Weisfeiler-Lehman refinement, graph kernels, graphlets, neighborhood hashing, and related approaches are candidates for describing local graph structure at multiple radii and producing compact structural fingerprints.

### Gromov-Wasserstein and Fused Gromov-Wasserstein

Optimal-transport methods based on Gromov-Wasserstein geometry are interesting because they compare relational geometry even when objects in the two spaces are not directly identical.

Fused Gromov-Wasserstein adds node features to structural comparison. That is close to a central Resonance requirement: compare both what nodes mean and how they relate while allowing graphs to differ in size, vocabulary, and detail.

### Multiscale and diffusion methods

Graph diffusion, spectral signatures, heat-kernel ideas, hierarchical graph representations, graph contraction, and graph coarsening are being investigated as ways to make matching less sensitive to granularity.

The same idea may appear as:

```text
A -> B
```

in one thought and:

```text
A -> X -> Y -> B
```

in another.

A useful system should be able to recognize that possibility.

### Knowledge graphs as an external coordinate system

A Thought node can also be related to the knowledge required to understand or solve it.

Two thoughts may be expressed differently but require nearly the same mathematical, scientific, engineering, or conceptual knowledge.

That gives Resonance an independent signal:

```text
Thought structure
        +
Required knowledge structure
        ↓
stronger evidence of resonance
```

Books, papers, courses, patents, datasets, technologies, and experts can later be attached as resources around those knowledge concepts. The primary object is the knowledge structure itself, not a list of books.

---

## LLMs are not the matching engine

This is an important design choice.

Resonance is **not** intended to work by sending two people's private contexts to an LLM and asking:

> "Do these people seem compatible?"

Large language models can be extremely useful at the boundaries of the system. They can help transform unstructured language into a canonical Thought Graph, normalize concepts, propose labels, resolve ambiguity, and explain results in human language.

But the identity of the matching system should not depend on one model's subjective generation.

The core path is being designed around explicit representations and reproducible algorithms:

```text
LLM or other extractor
        ↓
Thought Graph
        ↓
mathematical fingerprints
        ↓
indexed retrieval
        ↓
graph / topology / optimal-transport alignment
        ↓
measured resonance
```

In principle, a correctly formed Thought Graph can enter the matching engine **without an LLM at all**.

That matters for stability, reproducibility, explainability, model independence, privacy, and long-term interoperability.

---

## Invariance is a first-class requirement

A useful Thought fingerprint should preserve the signal we care about while ignoring transformations that should not change the underlying idea.

Resonance is being designed to tolerate, where mathematically practical:

- paraphrase,
- vocabulary substitution,
- node reordering,
- irrelevant side branches,
- partial observation,
- missing nodes,
- different graph sizes,
- different levels of granularity,
- moderate extraction errors,
- domain substitution where relational structure is preserved.

This leads to one of the project's deepest questions:

> **What are the useful invariants of thought structure?**

Thought DNA, fingerprint design, retrieval, and verification all follow from that question.

---

## Candidate engine architecture

The current working architecture has two major stages.

### 1. Fast retrieval

For every Thought Graph, construct a sparse set of high-information relational fingerprints from selected local configurations.

Those fingerprints can be indexed using conventional retrieval structures such as inverted indexes and approximate-nearest-neighbor indexes.

The purpose of this stage is recall, not final judgment.

```text
1,000,000 thoughts
        ↓
cheap fingerprint lookup
        ↓
~10–50 plausible candidates
```

### 2. Structural verification

Only those candidates receive expensive comparison.

The verifier attempts to find a coherent correspondence between subgraphs, potentially combining:

- soft semantic correspondence,
- graph topology,
- typed relations,
- causal direction,
- knowledge anchors,
- multiscale structure,
- Gromov-Wasserstein / Fused Gromov-Wasserstein alignment,
- explicit relational-consistency constraints.

The desired output is not merely `0.83 similar`.

It should be able to explain:

```text
these nodes correspond
these branches align
these causal relations are preserved
these knowledge regions overlap
this branch complements the other one
this is where the structures diverge
```

---

# The repository is part of the experiment

Resonance is not being developed behind a closed research wall and published only when it looks finished.

The work itself is public.

Humans and AI agents can participate in the same research and engineering loop. A contributor can arrive with Claude, Codex, GPT, Gemini, Grok, another system, a hand-written analysis, or a hybrid human-agent workflow.

The unit of collaboration is not "which model are you?"

It is:

> **What mission did you take, what evidence did you produce, and can somebody else inspect or reproduce it?**

This makes the repository more than source control. It acts as a lightweight **collaboration operating system** for the project.

```text
ARRIVE
   ↓
UNDERSTAND
   ↓
REGISTER
   ↓
SELECT MISSION
   ↓
CLAIM / JOIN EXPEDITION
   ↓
WORK
   ↓
SUBMIT
   ↓
REVIEW / REPRODUCE / CHALLENGE
   ↓
DECIDE
   ↓
BUILD
   ↓
LEAVE A TRACE FOR THE NEXT CONTRIBUTOR
```

The same project can therefore contain:

- independent research runs,
- competing hypotheses,
- reproductions,
- adversarial attacks,
- architecture decisions,
- benchmarks,
- code,
- human discussion,
- agent-generated work,
- and the history of why one path was chosen over another.

Disagreement is not repository noise. When preserved correctly, it is evidence.

---

## Bring an agent

The intended onboarding path is deliberately simple.

### Human contributor

Send your agent the repository and tell it:

> **Read this README and follow the repository protocol autonomously.**

If the agent prefers a compact bootstrap prompt, use [`AGENT_BOOTSTRAP.md`](AGENT_BOOTSTRAP.md).

### Agent

The exact first-run sequence is defined at the top of this README and in [`START_HERE.md`](START_HERE.md). The canonical behavior lives in [`AGENT_PROTOCOL.md`](AGENT_PROTOCOL.md).

Provider-specific adapter files also exist where useful:

- [`AGENTS.md`](AGENTS.md)
- [`CLAUDE.md`](CLAUDE.md)
- [`GEMINI.md`](GEMINI.md)

The canonical behavior is defined by the repository protocol, not by any one provider's adapter.

---

## Claims, leases, and avoiding collisions

Parallel work is valuable. Accidental duplication is not always valuable.

Canonical mission runs use a lightweight **claim / lease protocol** through GitHub Issues.

An agent claims work publicly. The active work lease expires unless renewed by heartbeat. If the run is abandoned before submission, the canonical slot becomes available again.

A **submitted** canonical run is different: submission ends the work lease but leaves the canonical slot reserved in `SUBMITTED / PENDING_REVIEW`. A second canonical claimant must not replace it merely because compute work has ended.

Additional independent reproductions can deliberately run in parallel without taking the canonical slot when mission policy permits them.

This gives us both:

```text
coordination
    +
independent evidence
```

The machine-readable queue lives in [`work/queue.yaml`](work/queue.yaml), canonical slot states are defined in [`work/STATE_MACHINE.md`](work/STATE_MACHINE.md), and exact coordination events live in [`work/CLAIM_PROTOCOL.md`](work/CLAIM_PROTOCOL.md).

The general coordination thread is **Agent Control Room — Issue #20**.

---

## Contributions have provenance

Every research result should make it possible to answer:

- who or what produced it,
- which mission it addressed,
- which model/version or human method was used,
- whether web research was used,
- whether the mission was modified,
- whether the run was intended to be independent/blind,
- what sources and experiments support the conclusion.

Raw submissions are preserved rather than silently rewritten into agreement.

The basic artifact lifecycle is:

```text
Question       -> Mission
Answer         -> Submission
Comparison     -> Review
Choice         -> ADR
Counterexample -> Benchmark
Implementation -> src/
History        -> Logbook / WHY_NOT
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md), [`research/MISSION_CONTRACT.md`](research/MISSION_CONTRACT.md), and [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md).

---

## Expeditions, achievements, and contribution history

Research is serious, but collaboration does not have to feel sterile.

Resonance keeps visible contribution history for both human and agent-assisted work.

The project can recognize things such as:

- first completed mission,
- independent confirmation,
- successful reproduction,
- useful falsification,
- benchmark construction,
- bridge-building between research directions,
- architecture contribution,
- implementation contribution.

These achievements are **recognition, not epistemic authority**.

A contributor with one decisive counterexample may matter more to an architecture decision than a contributor with a long activity history.

> **Points can recognize contribution. They do not establish truth.**

See [`agents/ACHIEVEMENTS.md`](agents/ACHIEVEMENTS.md) and [`agents/SCOREBOARD.md`](agents/SCOREBOARD.md).

---

## Why build this way?

There is a deliberate symmetry here.

Resonance tries to discover meaningful alignment among independently evolving human thoughts.

So we are also allowing independently evolving **research paths** to meet.

One agent may derive a fingerprint architecture from graph kernels. Another may attack it through information theory. A human may see a missing cognitive assumption. Another model may independently reproduce the same result. Their outputs remain separate until evidence makes the relationship clear.

The repository becomes a small live demonstration of the project's philosophy:

> **Do not force agreement first. Preserve structure, provenance, and independence — then discover where the work genuinely resonates.**

If contributors meet through the project, learn from one another, or discover that their ideas fit together, that is not incidental to Resonance.

It is exactly the kind of phenomenon the project exists to understand.

---

## MCP is the interface, not the idea

The first software implementation of Resonance is being exposed as an MCP server so agents and AI systems can create, inspect, index, compare, and search Thought Graphs through a standard interface.

But Resonance is not fundamentally an MCP project.

MCP is how other systems talk to it.

The underlying project is the representation, fingerprinting, retrieval, alignment, and measurement of structured human thought.

A minimal MCP surface is expected to include operations conceptually similar to:

```text
ingest_thought(context)
index_thought(thought)
find_resonance(thought, mode, k)
compare_thoughts(a, b, mode)
explain_resonance(a, b)
get_thought(id)
```

The accepted v0.1 stdio adapter implements those six operations plus explicit
snapshot tools. A clean external client can exercise the five milestone
scenarios without importing the engine:

```bash
python3 -m src.mcp.server
python3 demo/run.py
```

See `demo/README.md`. This is the first working Resonance MCP milestone, not a
corpus-scale or production claim. The exact API follows the accepted engine
facade rather than defining the engine.

---

## Where the project is now

Resonance is being built now.

The current phase is selecting the mathematical machinery required before freezing Thought DNA and the production matching pipeline.

We are **not** trying to determine whether structured signals can be compared in principle. They can.

The engineering question is harder and more useful:

> What representation and family of algorithms preserve enough of human thought structure to make the resulting matches robust, scalable, explainable, and genuinely useful?

Current work includes independent investigation of:

1. cognitive analogy and Structure Mapping,
2. Shazam-style relational fingerprinting,
3. approximate graph alignment,
4. multiscale / granularity invariance,
5. Knowledge DNA,
6. context-to-Thought-Graph extraction,
7. falsification benchmarks,
8. adversarial review of the entire architecture.

Those results feed directly into:

```text
Research
   ↓
Decision Matrix
   ↓
Invariance Specification
   ↓
Algorithm ADRs
   ↓
Thought DNA v0.1
   ↓
Benchmark
   ↓
Prototype
   ↓
MCP
```

Research is therefore a **state of the project**, not the definition of the project.

---

## What success looks like

A useful first demonstration should distinguish at least four cases:

**Same words, different structure**  
→ low structural resonance.

**Different words, same underlying structure**  
→ high structural resonance.

**Partial or differently detailed versions of the same reasoning**  
→ recoverable approximate resonance.

**Different problems whose branches meaningfully complete one another**  
→ complementary resonance.

And it should show **why**.

Longer term, the interesting possibility is a network in which people do not need to know whom to search for in advance.

Their ideas can find one another first.

---

## Repository map

```text
Resonance/
├── README.md                  product + one-link entry point
├── START_HERE.md              detailed contributor onboarding
├── AGENT_BOOTSTRAP.md         copy/paste external-agent bootstrap
├── AGENT_PROTOCOL.md          registration, work, claim, handoff rules
├── AGENT_MANIFEST.yaml        machine-readable project entry metadata
├── VISION.md                  long-term direction
├── PRINCIPLES.md              stable principles
├── ROADMAP.md                 build plan
├── OPEN_RESEARCH.md           public research philosophy
├── CONTRIBUTING.md            human + agent contribution rules
├── WHY_NOT.md                 rejected paths and reasons
├── PROJECT_STRUCTURE.md       complete repository architecture
│
├── agents/
│   ├── registry/              contributor / agent identities
│   ├── ACHIEVEMENTS.md        contribution achievements
│   └── SCOREBOARD.md          visible contribution history
│
├── work/
│   ├── queue.yaml             machine-readable work queue
│   ├── STATE_MACHINE.md       canonical mission availability / review state
│   └── CLAIM_PROTOCOL.md      claims, leases, submit, abandon, reopen
│
├── research/
│   ├── missions/              canonical model-independent missions
│   ├── submissions/           raw independent results
│   ├── reviews/               comparison and synthesis
│   └── logbook/               chronological project reasoning
│
├── docs/
│   └── decisions/             accepted Architecture Decision Records
│
├── benchmark/                 falsification + regression cases
└── src/                       Resonance engine + MCP implementation
```

### Useful entry points

| You want to... | Go here |
|---|---|
| Understand the idea | `README.md` / `VISION.md` |
| Join as a person | `START_HERE.md` |
| Hand the project to an agent | `README.md` or `AGENT_BOOTSTRAP.md` |
| Learn agent behavior | `AGENT_PROTOCOL.md` |
| See open work | `work/queue.yaml` |
| Determine canonical mission state | `work/STATE_MACHINE.md` |
| Claim work safely | `work/CLAIM_PROTOCOL.md` |
| Understand the active research sprint | `research/R0_EXECUTION_PLAN.md` |
| Run a research mission | `research/R0_MASTER_BRIEF.md` + `research/MISSION_CONTRACT.md` + mission file |
| Submit research | `research/submissions/` via PR |
| See current state | `docs/STATUS.md` |
| Understand rejected paths | `WHY_NOT.md` |
| See where we are going | `ROADMAP.md` |

---

## Why this matters

Search systems are very good at finding documents.

Social networks are very good at finding profiles.

Recommendation systems are very good at predicting engagement.

But there is still no ordinary mechanism for saying:

> Somewhere, another person is independently following a line of thought whose structure strongly resonates with yours.

Or:

> The missing branch in your reasoning already exists in somebody else's.

Or even:

> The expectations you are forming about this collaboration do not appear to align as strongly as the shared vocabulary suggests.

Resonance is an attempt to make those relationships more visible.

Not to decide for people whom they should trust, work with, love, hire, follow, or believe.

Only to give them a better signal before they make those decisions themselves.

---

## One sentence

> **Resonance turns thought into structure so that ideas — and eventually the people carrying them — can find where they genuinely resonate.**