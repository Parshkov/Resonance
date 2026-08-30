# Resonance

**Resonance** is an experimental MCP project for discovering structural resonance between independently evolving human thoughts.

The core idea is not `people -> profiles -> connections`, but:

> **thought -> structural / semantic resonance -> person**

The research hypothesis is that a human thought can be represented as a typed relational graph and searched by sparse multiscale relational fingerprints, with expensive structural verification applied only to retrieved candidates.

## Core research question

Can we detect isomorphic, approximately isomorphic, causally analogous, or complementary subgraphs inside independently evolving Thought Graphs — including cases where vocabulary and domain differ?

Example:

```text
battery
  -> heat accumulation
  -> degradation
  -> failure
```

and

```text
organization
  -> information accumulation
  -> coordination degradation
  -> failure
```

The surface semantics differ, while the relational / causal structure may be analogous.

## Candidate architecture

```text
Human context
  -> Thought extraction
  -> Thought Graph
  -> sparse relational / structural fingerprints
  -> cheap candidate retrieval
  -> structural verification of top-K candidates
  -> resonance explanation
```

The working inspiration is:

**Shazam × MAC/FAC × Structure Mapping × modern graph alignment**

This is a hypothesis, not a commitment. Research Sprint R0 exists to falsify or refine it before Thought DNA is frozen.

## Design constraints

- MVP research + implementation window: **40–60 hours**
- No new large model training
- LLMs may extract / normalize / label / explain, but should not be the core comparison engine
- Typical Thought Graph initially: ~10–100 nodes
- Future corpus: potentially millions of Thoughts
- Retrieval must be cheap; expensive verification may run only on top-K candidates
- Must tolerate paraphrase, noise, partial observation, different graph sizes and granularity
- Cross-domain structural analogy matters
- Explainability matters: the engine should show which branches correspond and why

## Repository map

- `research/` — Research Sprint R0 briefs and returned reports
- `docs/` — architecture decisions, invariance spec, Thought DNA, scoring model
- `benchmark/` — falsification dataset and evaluation protocol
- `src/` — implementation after the research gate

## Current phase

**R0 — scientific / algorithmic research.**

We do not freeze Thought DNA until the first research gate is complete.

See `docs/ARCHITECTURE_LOOP.md` and `docs/STATUS.md`.
