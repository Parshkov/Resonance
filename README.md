# Resonance

> **Shazam for human thought.**

**Resonance** is a system for finding people whose thoughts, ideas, problems, expectations, or lines of reasoning meaningfully resonate — even when they use different words, work in different fields, or do not yet know that they should meet.

It starts from a simple human problem.

We spend a great deal of our lives trying to find people who will understand what we mean, care about the same problem, see the same hidden structure, or continue a thought from the point where ours currently ends. We search through job titles, biographies, social graphs, keywords, communities, introductions, and chance conversations.

And we are often wrong.

Not necessarily because anyone behaved badly. Human beings naturally form expectations about other people before we have enough evidence that our internal models actually align. We confuse shared vocabulary with shared reasoning, shared profession with shared interests, and apparent similarity with genuine compatibility.

Resonance asks whether we can make part of that alignment **observable**.

Instead of asking:

> Who has a similar profile?

or even:

> Who says they are interested in the same thing?

we want to ask:

> **Whose current thought has a structure that meaningfully matches mine?**

The core direction is:

```text
thought
  -> structured signal
  -> resonance
  -> person
```

Not:

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

A thought is obviously not audio, and we do not expect one literal Shazam algorithm to solve human reasoning. The analogy is architectural:

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

If a human thought can be converted into a sufficiently stable relational signal, then comparison becomes a mathematical problem rather than a matter of asking a language model whether two texts "feel similar."

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

The domains are different. The nouns are different. A conventional semantic similarity system may place them far apart.

But their relational pattern may be strongly analogous:

```text
system
  -> accumulating intermediary effect
  -> degradation of function
  -> failure
```

Resonance therefore treats a thought as a **relational object**, not merely a paragraph or embedding.

Our working representation is a typed Thought Graph: a graph whose nodes may describe problems, goals, hypotheses, mechanisms, constraints, evidence, methods, concepts, knowledge requirements, or outcomes, and whose edges describe meaningful relationships between them.

The exact Thought DNA is being engineered now. We intentionally do not freeze the schema before the matching mathematics tells us what information it actually needs.

---

## What Resonance is trying to detect

The goal is broader than ordinary similarity.

Given independently evolving Thought Graphs, Resonance should be able to discover useful cases of:

### Direct resonance

Two people are independently thinking about substantially the same problem or idea.

### Approximate structural resonance

The structures are closely related but contain noise, missing nodes, different levels of detail, or different decompositions.

### Analogical resonance

The surface domains differ, but important relational or causal subgraphs align.

### Complementary resonance

The thoughts are not the same, but one contains a branch, method, knowledge region, or continuation that meaningfully connects to the other.

The last case may eventually be one of the most valuable.

Sometimes the person we need is not someone who already thinks exactly like us.

It is someone whose thought **begins where ours ends**.

---

## The mathematical problem

At a high level, the project can be described as:

> **Find isomorphic, approximately isomorphic, causally analogous, or complementary subgraphs inside independently evolving human Thought Graphs.**

A naive implementation would embed an entire thought into one vector and compare cosine similarity.

We are deliberately aiming for something stronger.

A Thought Graph should produce multiple signals describing different aspects of the thought, potentially including:

- semantic meaning,
- relational structure,
- causal structure,
- functional role,
- local graph topology,
- multiscale neighborhood structure,
- required knowledge,
- confidence and provenance.

A useful resonance score may therefore look more like a structured alignment than a single similarity number.

Conceptually:

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

It is whether **many independent local correspondences agree on one coherent relational mapping**.

That is the Thought-Graph analogue of the principle that makes audio fingerprinting robust.

---

## Scientific foundations

Resonance is not based on one paper or one algorithm. It combines ideas from several mature areas of mathematics, computer science, and cognitive science.

### Structure Mapping and analogy

Work on Structure-Mapping Theory and the Structure-Mapping Engine provides an important foundation for distinguishing superficial similarity from relational analogy.

The key idea is highly relevant to Resonance: deep analogy depends less on matching object attributes and more on preserving **systems of relations** between objects.

MAC/FAC adds another useful architectural lesson: use a cheap first stage to retrieve plausible candidates, then spend substantially more computation on structural verification only for a small set of candidates.

### Graph fingerprints and Weisfeiler-Lehman methods

Weisfeiler-Lehman refinement, graph kernels, graphlets, neighborhood hashing, and related methods provide ways to describe local graph structure at several radii.

They are candidates for building compact structural fingerprints of Thought Graph neighborhoods rather than comparing every graph against every other graph directly.

### Gromov-Wasserstein and Fused Gromov-Wasserstein

Optimal-transport methods based on Gromov-Wasserstein geometry are interesting because they can compare **relational geometry** even when the objects in two spaces are not directly identical.

Fused Gromov-Wasserstein extends that idea by combining structural relationships with node features.

That is close to a central Resonance requirement: compare both what nodes mean and how they relate, while allowing graphs to differ in size, vocabulary, and detail.

### Multiscale and diffusion methods

Graph diffusion, spectral signatures, heat-kernel ideas, hierarchical graph representations, and graph coarsening are being investigated as ways to make matching less sensitive to granularity.

The same idea may appear as:

```text
A -> B
```

in one thought and:

```text
A -> X -> Y -> B
```

in another.

A useful system must be able to recognize that possibility without treating every inserted intermediate concept as a completely different structure.

### Knowledge graphs as an external coordinate system

Each Thought node can also be related to the knowledge needed to understand or solve it.

Two thoughts may be expressed differently but require nearly the same mathematical, scientific, engineering, or conceptual knowledge.

This gives Resonance another independent signal:

```text
Thought structure
        +
Required knowledge structure
        ↓
stronger evidence of resonance
```

Books, papers, courses, patents, datasets, technologies, and experts can later be attached as evidence or resources around those knowledge concepts. The primary object is the knowledge structure itself, not a list of books.

---

## LLMs are not the matching engine

This is an important design choice.

Resonance is **not** intended to work by sending two people's private contexts to an LLM and asking:

> "Do these people seem compatible?"

Large language models can be extremely useful at the boundaries of the system. They can help transform unstructured language into a canonical Thought Graph, normalize concepts, propose labels, resolve ambiguity, and explain a result in human language.

But the identity of the system should not depend on one model's subjective generation.

The core matching engine is being designed around explicit representations and reproducible algorithms:

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

This matters for stability, reproducibility, explainability, model independence, privacy, and long-term interoperability.

LLMs may change.

The structure being compared should remain inspectable.

---

## Invariance is a first-class requirement

A good Thought fingerprint should preserve the signal we care about while ignoring transformations that should not change the underlying idea.

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

The current working architecture has two main stages, inspired by both large-scale fingerprint retrieval and MAC/FAC-style analogy search.

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

The output is not merely `0.83 similar`.

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

## MCP is the interface, not the idea

The first implementation of Resonance is being exposed as an MCP server so that agents and AI systems can create, inspect, index, compare, and search Thought Graphs through a standard interface.

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

The exact API will follow the core architecture rather than define it prematurely.

---

## Where the project is now

Resonance is being built now.

The current phase is focused on selecting the correct mathematical machinery before freezing Thought DNA and the production matching pipeline.

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

A useful first demonstration should be able to take independently authored thoughts and correctly distinguish at least four cases:

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

## Repository map

```text
research/   independent scientific and algorithmic investigations
docs/       architecture decisions, invariance spec, Thought DNA, scoring
benchmark/  controlled transformations, hard negatives, evaluation
src/        Resonance engine and MCP implementation
```

See:

- `research/R0_MASTER_BRIEF.md`
- `research/R0_AGENT_MISSIONS.md`
- `docs/ARCHITECTURE_LOOP.md`
- `docs/STATUS.md`

---

## One sentence

> **Resonance turns thought into structure so that ideas — and eventually the people carrying them — can find where they genuinely resonate.**
