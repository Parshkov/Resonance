# Why Not?

This is a living record of tempting approaches Resonance deliberately does **not** adopt by default.

The purpose is not to declare ideas permanently wrong. It is to preserve reasoning so the project does not repeatedly rediscover the same dead ends.

## Why not just compare whole-thought embeddings?

A single embedding is excellent for topical/semantic retrieval but collapses internal relational structure. It can score "same words, different reasoning" too highly and miss "different domain, same causal structure." Embeddings may remain one signal, but not the definition of resonance.

## Why not ask an LLM whether two people/thoughts match?

That is difficult to reproduce, expensive at scale, model-dependent, hard to audit, and weak as a stable protocol between independent systems. LLMs are useful for extraction and explanation, not as the only judge.

## Why not freeze Thought DNA immediately?

A schema chosen before the matching mathematics is known risks preserving information the engine never uses while omitting information it critically needs. R0 derives representation requirements from invariances, fingerprints, alignment, and extraction reliability.

## Why not exact graph isomorphism?

Human Thought Graphs will differ in vocabulary, missing nodes, graph size, noise, and granularity. Exact isomorphism is useful as a special case and test oracle, not a complete matching strategy.

## Why not train a graph neural network first?

The first sprint has little labeled data, a short engineering budget, and a strong requirement for explainability and reproducibility. A learned graph model may become useful later, but it should first have a deterministic benchmark to beat.

## Why not build a universal knowledge graph first?

It would consume the project. R0 only needs an interface for knowledge anchors and a small practical coordinate system sufficient to test whether knowledge overlap adds independent signal.

## Why not build federation/privacy/introductions now?

Those are important product directions, but they depend on having a useful resonance signal. The first milestone is to prove the representation/retrieval/alignment loop locally.

## Why not optimize for one model vendor?

The comparison engine should survive model churn. The project intentionally uses multiple model families in research and keeps the mathematical core separable from extraction providers.

## Additions

When rejecting an approach, add:

- date;
- approach;
- why it was tempting;
- evidence against it;
- whether rejection is permanent or conditional;
- what new evidence would justify revisiting it.