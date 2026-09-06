# Resonance Research Program

Research in this directory exists to make concrete architecture decisions for the Resonance engine.

It is not a collection of essays. Every mission should either narrow an engineering choice, produce a benchmark, challenge an assumption, or change the required Thought DNA.

## Structure

```text
research/
├── README.md
├── R0_MASTER_BRIEF.md
├── R0_EXECUTION_PLAN.md
├── MISSION_CONTRACT.md
├── missions/
│   ├── R0_A_STRUCTURE_MAPPING.md
│   ├── R0_B_RELATIONAL_FINGERPRINTING.md
│   ├── R0_C_GRAPH_ALIGNMENT.md
│   ├── R0_D_MULTISCALE.md
│   ├── R0_E_KNOWLEDGE_DNA.md
│   ├── R0_F_THOUGHT_EXTRACTION.md
│   ├── R0_G_BENCHMARK.md
│   └── R0_H_RED_TEAM.md
├── submissions/
├── reviews/
└── logbook/
```

The older aggregate `R0_AGENT_MISSIONS.md` is retained for historical convenience. The canonical task definitions are now the individual files under `missions/`.

## R0 objective

R0 answers one practical question:

> What representation and family of algorithms should Resonance use before we freeze Thought DNA and implement the core engine?

## Critical independence

B and C each have two first-party independent runs:

- B1 GPT-5.6 Sol MAX
- B2 Claude Opus 5
- C1 Claude Opus 5
- C2 GPT-5.6 Sol MAX

Do not share B1/B2 or C1/C2 with one another before both sibling submissions exist.

## From research to architecture

A submission is evidence, not a decision.

```text
submissions
  -> reviews
  -> Decision Matrix
  -> Invariance Specification
  -> ADRs
  -> Thought DNA
  -> benchmarked prototype
```

Accepted architecture decisions live under `docs/decisions/`.

## Reproducing a mission

Read the master brief and mission contract, then run the mission file unchanged. Record model/version and tool use in the submission header. Independent reproductions by other models or humans are explicitly welcome.