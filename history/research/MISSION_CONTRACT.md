# Research Mission Contract

A **Mission** is a model-independent research task that should produce an architecture-relevant decision.

Do not treat missions as casual prompts. They are reproducible units of work.

## Required inputs

Every mission inherits:

- `research/R0_MASTER_BRIEF.md` for project context and constraints;
- one mission definition from `research/missions/`;
- no sibling submission when the run is marked independent.

## Required behavior

The researcher or agent must:

1. answer the decision question rather than survey the field broadly;
2. challenge the project's current hypothesis when evidence warrants it;
3. prefer primary/authoritative sources;
4. identify existing implementations and dependency risks;
5. state what representation the recommended algorithm requires;
6. state supported and unsupported invariances;
7. give realistic computational cost;
8. propose a small falsification experiment;
9. name failure modes and tempting approaches to reject;
10. end with a GO / NO-GO style conclusion where applicable.

## Required submission format

Unless a mission explicitly overrides it, use:

```markdown
---
mission: R0-X
run: X1
contributor: <name/handle>
agent_or_model: <model/version or human>
date: YYYY-MM-DD
mission_modified: false
web_research_used: true
---

# Decision
# Confidence
# Best Algorithm / Method
# Why It Fits Resonance
# Required Thought DNA
# Required Graph Representation
# Invariances
# Retrieval vs Verification
# Computational Cost
# Existing Implementations
# Minimal Pseudocode
# Toy Experiment
# Failure Modes
# What NOT To Build
# Architecture Consequences
# Sources
```

## Invariance table

Cover these baseline transformations unless the mission is unrelated:

| ID | Transformation |
|---|---|
| A | paraphrase |
| B | vocabulary substitution |
| C | node ordering |
| D | insertion of irrelevant branches |
| E | partial observation / missing nodes |
| F | different granularity |
| G | different graph sizes |
| H | domain substitution with relational structure preserved |
| I | modest extraction mistakes |

## Independence contract

If an issue says a run is independent:

- do not read the sibling report;
- do not feed it to the model;
- do not use another agent to summarize it first;
- state any accidental exposure in the provenance header.

This rule exists to reduce anchoring and give the project evidence about independent convergence.

## Model/tool metadata

Record the actual model and mode used as precisely as practical. Also state whether web search, code execution, external tools, or additional agents were used.

Do not include credentials or hidden chain-of-thought. A concise description of method and evidence is sufficient.

## Acceptance

A report is useful when another contributor can determine:

- what was recommended;
- why;
- what would make it wrong;
- what Thought DNA fields it forces us to preserve;
- how to test it quickly.

Longer is not automatically better.