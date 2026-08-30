# R0-F — Context to Thought Graph

Read `research/R0_MASTER_BRIEF.md` and `research/MISSION_CONTRACT.md` first.

## Decision question

How should unstructured human language/context be transformed into a canonical-enough Thought Graph for a non-LLM comparison engine?

LLMs are allowed here. The matching engine itself should not depend on an LLM judgment.

## Resolve

1. What information can an LLM extract reliably enough to become graph structure?
2. Which distinctions are too unstable to trust in v0.1?
3. What minimal node taxonomy is reliably extractable?
4. What minimal edge taxonomy is reliably extractable?
5. Should causal, prerequisite, supports, contradicts, part-of, goal, constraint, and similar relations remain distinct?
6. How is extraction uncertainty represented?
7. How does every extracted claim retain provenance to source text/context?
8. How can repeated extraction of the same meaning produce approximately canonical graphs?
9. How do we prevent/measure hallucinated relations?
10. One-pass extraction or staged extraction + normalization?
11. How can a manually authored Thought Graph bypass the LLM entirely?

## Required artifact

Design an extraction contract and provide 2–3 example Thought Graphs in JSON.

Do **not** globally finalize Thought DNA. Report only the schema elements the extraction layer can plausibly supply and how reliable each is.