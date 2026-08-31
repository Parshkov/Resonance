# Research Reviews

Reviews turn independent submissions into architecture-relevant conclusions.

Do not use this directory for raw agent output. Raw runs belong in `research/submissions/`.

## A good comparative review answers

1. Where did independent runs converge without seeing each other?
2. Where did they disagree?
3. Which assumptions caused the disagreement?
4. Is the disagreement empirical, mathematical, representational, or merely terminological?
5. What small experiment can resolve it?
6. What requirements do both answers impose on Thought DNA?
7. Which recommendation should proceed to an ADR, and with what confidence?

## Recommended structure

```markdown
# Scope
# Inputs Reviewed
# Independent Convergence
# Material Disagreements
# Assumption Matrix
# Experiments Needed
# Consequences for Thought DNA
# Recommended Architecture Decision
# Confidence
# Open Questions
```

## R0 priority reviews

The first mandatory comparative reviews are:

```text
B1 vs B2 -> fingerprint retrieval review
C1 vs C2 -> structural verifier review
```

After those, synthesize A/D/E/F/G/H around the candidate architecture.

## Current synthesis

- [R0 architecture synthesis](R0_SYNTHESIS_parshkov-openai-gpt5-codex-s7d3.md)
- Independent review of the reserved R0-SYNTHESIS revision: `R0_SYNTHESIS_review_parshkov-xai-grok46-k3e8.md` (review input, not a replacement canonical run).

A review does not erase minority conclusions. When uncertainty remains, preserve it in the ADR and state what evidence would trigger reconsideration.
