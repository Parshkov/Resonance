# Open Research Program

Resonance develops its scientific and engineering reasoning in public.

The repository is intended to show not only the final code, but also how humans and AI agents arrive at the architecture: missions, independent runs, disagreements, failures, reviews, decisions, and revisions.

This is useful for two reasons.

First, Resonance itself is about making hidden relationships between thoughts more observable. Keeping the project's own reasoning legible is consistent with that goal.

Second, research produced by frontier models should be reproducible and criticizable. A good answer should not disappear into a private chat after influencing the codebase.

## The public loop

```text
Question
  -> Mission
  -> independent submissions
  -> adversarial / comparative review
  -> experiment or benchmark
  -> architecture decision
  -> implementation
  -> new evidence
  -> revision when necessary
```

## Repository locations

```text
research/missions/       canonical mission definitions
research/submissions/    raw returned work from humans/agents
research/reviews/        comparison and adversarial review
docs/decisions/          accepted Architecture Decision Records
research/logbook/        chronological reasoning and project notes
benchmark/               tests capable of falsifying claims
WHY_NOT.md               rejected approaches and reasons
```

## Missions, not vendor prompts

A mission describes an intellectual task independently of the model used to execute it. The same mission can be run by Claude, GPT, Grok, another agent, or a person.

Model-specific configuration belongs in the execution metadata, not in the scientific question.

This lets us ask useful questions such as:

- Do different model families independently reach the same architecture decision?
- Where do they disagree?
- Which disagreement can be resolved experimentally?
- Does one model family repeatedly favor a class of methods?
- Can a human contributor reproduce or invalidate an agent conclusion?

## Independence is deliberate

For critical decisions, seeing another answer before producing your own creates anchoring. The project therefore uses blind/independent runs where appropriate.

Independent outputs are not wasted duplication. They are a way to estimate the stability of an architecture conclusion.

## Public does not mean careless

Do not publish:

- API keys or credentials;
- private user context;
- proprietary third-party data;
- copyrighted material beyond appropriate citation/quotation;
- secrets embedded in model transcripts.

Research reports should contain the reasoning necessary to reproduce a decision, not private chain-of-thought or hidden system prompts.

## Contributors

A contributor can participate with expertise, compute, model access, criticism, benchmark examples, implementation, or review.

If someone wants to donate model tokens/compute, the most useful approach is usually to take an open independent mission and return a provenance-labeled submission rather than simply running a broad 'research Resonance' prompt.

See `CONTRIBUTING.md` and `research/R0_EXECUTION_PLAN.md` for the current work.