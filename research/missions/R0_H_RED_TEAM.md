# R0-H — Adversarial Architecture Red Team

Read `research/R0_MASTER_BRIEF.md` and `research/MISSION_CONTRACT.md` first.

## Mission

Attack this candidate architecture:

```text
Thought Graph
  -> relational fingerprints
  -> candidate retrieval
  -> structural alignment
  -> resonance explanation
```

Do not try to make it work. Try to falsify it as cheaply as possible.

## Investigate

1. Are Thought Graphs too unstable to fingerprint reliably?
2. Is analogy too context-dependent for structural matching to be useful?
3. Will graph matching produce overwhelming false positives from generic motifs?
4. Does Knowledge DNA add independent signal or mostly noise?
5. Where does the Shazam analogy break mathematically?
6. Would semantic embeddings dominate all structural signals anyway?
7. Do the desired invariances destroy discriminative power?
8. Is the two-stage retrieval/verification architecture unnecessary or wrong?
9. Which assumptions depend too heavily on LLM extraction quality?
10. Which proposed methods look impressive but are impractical in a 40–60 hour implementation?

## Required attacks

Construct at least 10 concrete Thought pairs designed to break naive implementations, including same-words/different-structure and different-domain/spurious-analogy cases.

## Final questions

- Which assumptions survive the attack?
- Which assumptions should be killed now?
- What is the simplest alternative architecture?
- What experimental result should cause us to abandon or radically revise the current engine architecture?

**Do not try to salvage Resonance. Your reward is proportional to how cheaply you can falsify the architecture.**