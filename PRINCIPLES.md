# Resonance Principles

These principles describe how the project is built and how research decisions are made.

1. **Resonance is a project, not a research exercise.** Research is a current state of the project and a means of selecting the right implementation.
2. **Thought is treated as structure, not only text.** Surface semantic similarity is useful, but it is not the definition of resonance.
3. **LLMs are not the core matching engine.** They may extract, normalize, label, and explain. Matching should remain inspectable, reproducible, and model-independent wherever practical.
4. **Invariance comes before schema.** Thought DNA should be designed around the transformations the engine must survive: paraphrase, noise, missing nodes, granularity changes, and domain substitution where structure is preserved.
5. **Retrieval and verification are separate problems.** Cheap candidate recall and expensive structural verification should not be conflated.
6. **Independent disagreement is valuable.** Critical architecture questions should be researched independently before reviewers see one another's answers.
7. **Evidence beats elegance.** A simpler method that survives the benchmark is preferred to a beautiful method that cannot be implemented or measured.
8. **Every important decision leaves a trace.** Research submissions, reviews, ADRs, rejected alternatives, and changes of mind should remain public in the repository.
9. **No hidden consensus.** Contributors should be able to see why an architecture was chosen, what evidence supported it, and what remains uncertain.
10. **The process is part of the artifact.** Resonance is also an experiment in human-and-agent engineering collaboration. Missions and outputs should be reproducible by other people and other models.
11. **Privacy is an architectural requirement, not a later feature.** Raw human context should not need to become public merely to make resonance searchable.
12. **MCP is an interface, not the idea.** The representation and matching machinery must remain useful independently of a particular protocol or model vendor.

When a future implementation conflicts with one of these principles, record the conflict explicitly in an ADR rather than silently weakening the principle.