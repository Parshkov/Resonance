# Contributing to Resonance

Resonance is developed in public. Contributions may be produced by people, AI agents, or human-agent teams. What matters is traceability, reproducibility, and usefulness.

## Ways to contribute

You can contribute by:

- running an open research mission with another model or methodology;
- challenging an existing result;
- adding a benchmark case or adversarial example;
- reviewing two conflicting submissions;
- proposing an Architecture Decision Record (ADR);
- implementing a benchmarked component;
- documenting a failed approach and why it failed.

## Research contributions

Start with:

1. `PRINCIPLES.md`
2. `research/R0_MASTER_BRIEF.md`
3. `research/MISSION_CONTRACT.md`
4. the relevant file under `research/missions/`
5. `research/R0_EXECUTION_PLAN.md`

Do not silently modify a mission before running it. If you believe the mission itself is flawed, open an issue or submit a revised mission as a separate proposal.

### Submission naming

Use:

```text
research/submissions/<mission>_<run>_<model-or-contributor>.md
```

Examples:

```text
R0_B3_fingerprinting_grok46.md
R0_C3_alignment_alice_manual.md
R0_H2_redteam_claude.md
```

### Required provenance header

Every research submission should begin with:

```yaml
mission: R0-B
run: B3
contributor: name-or-handle
agent_or_model: model/version or "human"
date: YYYY-MM-DD
mission_modified: false
web_research_used: true/false
notes: optional
```

Never include API keys, private prompts containing secrets, private human context, or credentials.

## Independence rule

Some missions intentionally have independent duplicate runs. If a run is marked independent, do not read the sibling result before submitting yours.

In particular, the first R0 sprint keeps these isolated:

- B1 from B2
- C1 from C2

Additional independent reproductions are welcome.

## Reviews

Reviews live under `research/reviews/`.

A review should not merely summarize. It should identify:

- conclusions that independently converge;
- direct contradictions;
- assumptions responsible for the disagreement;
- experiments capable of resolving it;
- consequences for Thought DNA and the benchmark.

## Architecture decisions

Accepted architecture belongs under `docs/decisions/` as ADRs. Research reports do not automatically become architecture.

An ADR must record:

- problem;
- considered options;
- evidence;
- decision;
- consequences;
- rejected alternatives;
- conditions that would cause reconsideration.

## Code contributions

Until the active architecture gate is complete, avoid implementing speculative core algorithms in `src/` merely because they are interesting. Prototype code used to test a research claim should be clearly marked as experimental.

Once an ADR exists, implementation should cite the ADR it implements and include the benchmark/tests relevant to the claim.

## AI-generated work

AI-generated research and code are welcome. Do not pretend AI output was manually authored. Naming the model/run is useful scientific metadata, not a stigma.

A model's confidence is not evidence. Sources, experiments, reproducibility, and benchmark results are evidence.

## Discussion style

Critique claims and architectures, not contributors. Strong disagreement is useful when it produces a falsifiable question or better test.

The goal is not to make every contributor agree. The goal is to make every important decision inspectable.