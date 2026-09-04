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
## Why not treat role-skeleton agreement as analogy? (2026-09-04)

- **Tempting because** it is fully vocabulary-invariant and makes every cross-domain relabelling "match".
- **Evidence against:** on Benchmark v0.2, engine 0.1 accepted 4/4 template coincidences (same skeleton, concept-free labels) as analogies; three unrelated 5-node graphs with the same skeleton scored structural 0.888. R0-H predicted exactly this.
- **Decision:** analogy requires abstract-concept correspondence from the deterministic lexicon (ADR-0004). Rejection is conditional: reconsider if a human-reviewed real corpus shows concept alignment adds nothing.

## Why not derive the OAuth issuer from the Host header? (2026-09-04)

- **Tempting because** it works behind any proxy without configuration.
- **Evidence against:** with two https origins configured, a caller-controlled `X-Forwarded-Host` became the issuer of every metadata document (metadata poisoning).
- **Decision:** the issuer comes from the configured allowlist; a header value is used only when it is itself an allowed origin (loopback excepted for local development). Permanent.

## Why not patch service classes at import time? (2026-09-04)

- **Tempting because** review fixes land as a small isolated delta.
- **Evidence against:** three `install()` shims silently rewrote eight methods of classes defined elsewhere; agents reading the classes could not see the real behaviour.
- **Decision:** folded into the classes (`src/persistence/projection.py`, `IdentityService._normalize_location`). Permanent.
