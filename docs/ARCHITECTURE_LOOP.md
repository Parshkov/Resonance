# Resonance Architecture Loop

The project is deliberately staged so implementation follows falsifiable architecture decisions rather than intuition or one persuasive model response.

## Public loop

```text
Question
→ canonical Mission
→ independent submission(s)
→ comparative / adversarial Review
→ Decision Matrix
→ Invariance Specification
→ Algorithm ADR(s)
→ Thought DNA v0.1
→ Benchmark
→ Prototype
→ Red Team
→ revise or freeze
→ MCP integration
```

Research artifacts remain public under `research/`; accepted architecture lives under `docs/decisions/`.

## Gate 1 — Research → Architecture

Do not start core implementation until we can answer all of these:

1. What transformations should Resonance be invariant to?
2. What is the fast retrieval representation?
3. What is the expensive verifier?
4. What information must Thought DNA preserve for both stages?
5. What information is useful but optional?
6. How will cross-domain analogy be separated from ordinary semantic similarity?
7. What benchmark would falsify the architecture?
8. What result constitutes PASS / FAIL?

The first mandatory independent comparisons are B1 vs B2 (fingerprinting) and C1 vs C2 (alignment).

## Gate 2 — Architecture → Prototype

Required artifacts:

- Decision Matrix
- `INVARIANCE_SPEC.md`
- retrieval ADR
- verification ADR
- Thought DNA v0.1 schema
- benchmark definition
- resonance scoring/explanation contract

An ADR should be specific enough that a coding agent can implement it without reinterpreting the entire research archive.

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

## Revision rule

No accepted decision is sacred. If new evidence contradicts an ADR, supersede it explicitly and preserve the old decision and reason for change.

Research reports are never retroactively edited to pretend they predicted the final architecture.

## Non-goals for the first 40–60 hours

- federated social network
- introduction / consent workflow
- global-scale knowledge graph ingestion
- cryptographic privacy protocol
- UI polish
- training a graph neural network
- generic social matching

The first deliverable is a demonstrated algorithmic principle for structural resonance.