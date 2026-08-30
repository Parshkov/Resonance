# Resonance Architecture Loop

The project is deliberately staged so that implementation follows falsifiable architecture decisions rather than intuition.

## Loop

```text
Independent research
→ Decision Matrix
→ Invariance Spec
→ Algorithm ADR
→ Thought DNA v0.1
→ Benchmark
→ Prototype
→ Red Team
→ Revise or freeze
→ MCP integration
```

## Gate 1 — Research → Architecture

Do not start production implementation until we can answer all of these:

1. What transformations should Resonance be invariant to?
2. What is the fast retrieval representation?
3. What is the expensive verifier?
4. What information must Thought DNA preserve for both stages?
5. What information is useful but optional?
6. How will cross-domain analogy be separated from ordinary semantic similarity?
7. What benchmark would falsify the architecture?
8. What result constitutes PASS / FAIL?

## Gate 2 — Architecture → Prototype

Required artifacts:

- `INVARIANCE_SPEC.md`
- retrieval ADR
- verification ADR
- Thought DNA v0.1 schema
- benchmark definition
- resonance scoring equation

## Gate 3 — Prototype → MCP

The algorithm must first work locally against the benchmark.

MCP should remain a thin interface around the verified core engine rather than becoming the place where algorithmic behavior is hidden.

Candidate MCP surface after the algorithmic gate:

```text
ingest_thought(context)
index_thought(thought)
find_resonance(thought, mode, k)
compare_thoughts(a, b, mode)
explain_resonance(a, b)
get_thought(id)
```

These names are provisional until the core data model is frozen.

## Non-goals for the first 40–60 hours

- federated social network
- introduction / consent workflow
- global-scale knowledge graph ingestion
- cryptographic privacy protocol
- UI polish
- training a graph neural network
- generic social matching

The first deliverable is a demonstrated algorithmic principle for structural resonance.
