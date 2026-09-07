# R0-C — Approximate Graph Alignment

Read `research/R0_MASTER_BRIEF.md` and `research/MISSION_CONTRACT.md` first.

## Decision question

Given two Thought Graphs of roughly 10–100 nodes, what practical verifier should determine whether they contain structurally analogous subgraphs, which nodes/relations correspond, and how strong that alignment is?

## Investigate and compare where relevant

- Graph Edit Distance
- maximum common subgraph
- subgraph isomorphism
- approximate graph matching
- quadratic assignment
- optimal transport
- Gromov-Wasserstein
- Fused Gromov-Wasserstein
- spectral graph matching
- SME-style constraint matching
- hybrid approaches

## Requirements

- graphs may differ in size;
- labels/vocabulary may differ;
- semantic node similarity is soft;
- structure matters strongly;
- partial matching matters;
- actual node/subgraph correspondence is required, not only a scalar;
- top-K is small enough to allow expensive verification.

## Resolve

1. Recommend one primary verifier and one fallback.
2. Decide whether a hybrid `soft correspondence -> structural consistency -> discrete mapping` is better than one algorithm.
3. Define the input features the verifier requires.
4. Define how unmatched nodes are handled.
5. Explain whether cross-domain analogy is possible without semantic collapse.
6. Provide an implementable scoring equation for Resonance.
7. State realistic runtime for 50x50-node graphs and top-20 candidate verification.
8. State what Thought DNA must preserve for the verifier to work.

This mission is run independently as C1 and C2. Do not inspect the sibling report before submitting.