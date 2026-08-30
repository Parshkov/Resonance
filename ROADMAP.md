# Resonance Roadmap

This roadmap is intentionally execution-oriented. The project is being built in a short architecture-to-prototype sprint, while keeping the research trail public.

## R0 — Scientific and algorithmic ground (hours 0–8)

Parallel independent missions:

- A — Structure Mapping and human analogy
- B1/B2 — Relational Constellation Fingerprinting, two independent runs
- C1/C2 — Approximate Graph Alignment, two independent runs
- D — Multiscale / granularity invariance
- E — Knowledge DNA / external knowledge coordinates
- F — Context → Thought Graph extraction
- G — Benchmark / falsification design
- H — adversarial architecture red team

Outputs are submitted under `research/submissions/`.

### Gate R0

Do not freeze Thought DNA until the following are produced:

- Decision Matrix
- Invariance Specification
- Retrieval ADR
- Verification ADR
- Thought DNA v0.1
- Benchmark v0.1
- initial Resonance scoring model

## R1 — Representation and benchmark (roughly hours 8–17)

- resolve conflicts between independent research runs
- define mandatory node/edge semantics
- define confidence and provenance
- specify allowed graph transformations
- create JSON Schema for Thought DNA v0.1
- create positive, hard-negative, analogy, and complementarity fixtures

## R2 — Extraction and canonicalization (roughly hours 17–24)

- text/context → Thought Graph
- provenance to source spans
- uncertainty handling
- repeatability / canonicalization tests
- manual graph input that bypasses LLMs

## R3 — Fast retrieval (roughly hours 24–32)

- landmark selection
- relational / multiscale fingerprints
- fingerprint entropy/commonness filtering
- inverted and/or ANN index
- recall@K benchmark

## R4 — Structural verification (roughly hours 32–40)

- candidate graph alignment
- partial correspondence
- topology / causal / semantic / knowledge signals
- structural-consistency checks
- explainable matched branches

## R5 — Red-team benchmark and tuning (roughly hours 40–45)

- same words / different structure
- different words / same structure
- noise insertion
- partial observation
- granularity changes
- cross-domain analogy
- generic motif false positives
- accidental semantic similarity

## R6 — MCP surface (roughly hours 45–52)

Expected conceptual operations:

```text
ingest_thought(context)
index_thought(thought)
find_resonance(thought, mode, k)
compare_thoughts(a, b, mode)
explain_resonance(a, b)
get_thought(id)
```

MCP wraps the engine; it does not define the engine.

## R7 — End-to-end demonstration (roughly hours 52–56)

Demonstrate at least:

1. same words, different structure → low structural resonance
2. different words, analogous structure → high analogical resonance
3. partial/different-granularity reasoning → recoverable match
4. complementary branches → useful complementary resonance

The system must explain why.

## R8 — Packaging and public record (roughly hours 56–60)

- tests and reproducibility
- architecture documentation
- README updates
- clean research provenance
- demo instructions
- known limitations
- next research questions

## Beyond the first sprint

Potential later directions include privacy-preserving fingerprints, federation between personal agents, human expectation matching, larger knowledge graphs, temporal evolution of Thought Graphs, and consent-based introductions. These are deliberately not allowed to block the first working engine.