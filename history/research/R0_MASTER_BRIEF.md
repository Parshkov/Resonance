# Resonance — Research Sprint R0 Master Brief

You are not writing a literature survey. You are making one concrete architecture decision for an experimental system called **Resonance**.

## Core hypothesis

A human thought can be represented as a typed relational graph.

Resonance should discover:

1. isomorphic subgraphs,
2. approximately isomorphic subgraphs,
3. structurally / causally analogous subgraphs,
4. potentially complementary subgraphs,

inside independently evolving human Thought Graphs.

The important case is **not merely semantic similarity**.

Example:

```text
battery
→ heat accumulation
→ degradation
→ failure
```

versus

```text
organization
→ information accumulation
→ coordination degradation
→ failure
```

The vocabulary and domains differ while the relational / causal structure may be analogous.

## Target pipeline

```text
Human context
→ Thought extraction
→ Thought Graph
→ sparse structural / relational fingerprints
→ very cheap candidate retrieval
→ expensive structural verification of top-K candidates
→ explanation of detected resonance
```

Candidate inspiration:

**Shazam + MAC/FAC + Structure Mapping + modern graph fingerprints / graph alignment**

Treat this only as a hypothesis. Challenge it.

## Hard constraints

- MVP engineering budget after research: roughly 40–50 hours.
- No training a new large ML model.
- Do not use an LLM as the core graph-comparison algorithm.
- LLMs may be used for extraction, normalization, labeling and explanations.
- Core comparison should preferably use deterministic or conventional numerical / graph algorithms.
- Typical Thought Graph: approximately 10–100 nodes initially.
- Eventually the corpus could contain millions of Thoughts.
- Candidate retrieval therefore must be extremely cheap.
- Expensive graph comparison may run only on top-K retrieved candidates.
- Thoughts may differ strongly in vocabulary.
- Thoughts may have different graph sizes and levels of detail.
- Thoughts will contain extraction errors and irrelevant nodes.
- Partial graphs must still be comparable.
- Cross-domain analogy is important.
- Explainability is important: we need to show which branches correspond and why.

Do not prematurely assume that Thought is a simple tree. It may need to be a directed property graph, multigraph, hypergraph, graph with reified relations, or another representation.

Choose representation only according to what the matching algorithm requires.

## Invariances of interest

Investigate which can realistically be supported:

A. paraphrase  
B. vocabulary substitution  
C. node ordering  
D. insertion of irrelevant branches  
E. partial observation / missing nodes  
F. different granularity (`A → B` vs `A → X → Y → B`)  
G. different graph sizes  
H. domain substitution while preserving relational structure  
I. modest extraction mistakes

## Hard negative

The algorithm must distinguish:

> same words, different structure

from

> different words, same structure

This distinction is central to the project.

## Research rules

1. Prefer original papers, authoritative implementations and primary sources.
2. Avoid generic AI articles.
3. Do not explain textbook material unless it changes an architecture decision.
4. Do not recommend a technique merely because it is fashionable.
5. Explicitly state when a promising method is impractical for this MVP.
6. Look for existing implementations/libraries that let us prototype instead of reimplementing papers.
7. If two methods should be combined, define exactly where each sits in the pipeline.
8. Think in terms of falsifiable experiments.
9. No hand-waving such as “use embeddings and graph neural networks.”
10. Do not expand scope into social networking, UI, federation or product strategy.

## Required output

Return one Markdown document, ideally <=3,000 words, using exactly this structure:

### Decision
One paragraph stating your recommendation.

### Confidence
HIGH / MEDIUM / LOW, plus the main uncertainty in <=100 words.

### Best Algorithm / Method
Exact technique(s), what is actually computed, equations where useful.

### Why It Fits Resonance
Tie the method explicitly to the requirements above.

### Required Thought DNA
List exactly what information each node and edge must contain for the method to work. Do not invent fields the algorithm does not use.

### Required Graph Representation
Tree / directed graph / multigraph / hypergraph / other, and why.

### Invariances

| Transformation | Supported | Partially | Not Supported | Mechanism |
|---|---|---|---|---|

Cover A–I.

### Retrieval vs Verification
State whether this method belongs in FAST RETRIEVAL, EXPENSIVE VERIFICATION, or BOTH. If retrieval, describe the index. If verification, describe inputs and output correspondence mapping.

### Computational Cost
Give realistic complexity and feasibility for:
- 50 nodes vs 50 nodes
- top 20 candidate comparisons
- corpus of 1M thoughts where relevant

### Existing Implementations
Libraries / repositories / packages that could let us prototype immediately. Prefer Python where practical. State maturity and dependency risks.

### Minimal Pseudocode
Actual algorithm, not conceptual prose.

### Toy Experiment
Design one experiment implementable in <=2 hours that could prove your recommendation wrong. Specify inputs, transformations, expected outcome and metric.

### Failure Modes
At least 5 concrete adversarial examples.

### What NOT To Build
Name tempting approaches to reject for this MVP and why.

### Architecture Consequences
Maximum 10 concrete bullets consumable by the later Thought DNA architect.

### Sources
Prefer 5–12 primary / authoritative references. For each, state exactly why it matters.

## Final rule

If the evidence does not support your proposed method, say **NO-GO**. We care more about eliminating bad architecture than defending the project.
