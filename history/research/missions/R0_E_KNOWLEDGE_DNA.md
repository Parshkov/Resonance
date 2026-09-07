# R0-E — Knowledge DNA / External Knowledge Space

Read `research/R0_MASTER_BRIEF.md` and `research/MISSION_CONTRACT.md` first.

## Decision question

Can external knowledge requirements provide an independent resonance signal, and what is the smallest useful representation for the first implementation?

Hypothesis: two Thought branches may be related if solving them requires strongly overlapping or nearby knowledge, even when their wording differs.

## Investigate possible anchors

- Wikidata / Wikipedia concept graph
- ACM Computing Classification System
- OpenAlex topics/concepts
- domain taxonomies
- prerequisite graphs
- ontology/concept embeddings where useful

## Resolve

1. What should a Thought node point to in knowledge space?
2. Distinguish **what this node is about** from **knowledge required to solve/understand this node**.
3. How should knowledge overlap/proximity be scored?
4. How should nearby but non-identical concepts be compared?
5. Where do books, papers, courses, patents, datasets, tools, and experts fit?
6. Does knowledge structure help cross-domain analogy, or mostly same-domain matching?
7. What can be implemented without building a universal ontology/ingestion pipeline?
8. What tiny interface should Thought DNA expose now so a richer Knowledge Graph can be added later?

## Required artifact

Propose `Knowledge DNA v0.1` as a minimal interface with example node annotations and a scoring mechanism. Mark clearly what is optional for the first benchmark.