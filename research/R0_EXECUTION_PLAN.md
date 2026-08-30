# R0 Execution Plan

R0 is the first public research sprint for Resonance. The goal is to resolve the mathematical and representational architecture before freezing Thought DNA.

## Runs

| Run | Mission | Primary executor | Independence | Expected output |
|---|---|---|---|---|
| A | Structure Mapping / human analogy | Claude Opus 5 | standalone | `submissions/R0_A_structure_mapping_opus5.md` |
| B1 | Relational Constellation Fingerprinting | GPT-5.6 Sol MAX | blind from B2 | `submissions/R0_B1_fingerprinting_gpt56.md` |
| B2 | Relational Constellation Fingerprinting | Claude Opus 5 | blind from B1 | `submissions/R0_B2_fingerprinting_opus5.md` |
| C1 | Approximate Graph Alignment | Claude Opus 5 | blind from C2 | `submissions/R0_C1_alignment_opus5.md` |
| C2 | Approximate Graph Alignment | GPT-5.6 Sol MAX | blind from C1 | `submissions/R0_C2_alignment_gpt56.md` |
| D | Multiscale / granularity invariance | GPT-5.6 Sol MAX | standalone | `submissions/R0_D_multiscale_gpt56.md` |
| E | Knowledge DNA | Grok 4.6 xhigh | standalone | `submissions/R0_E_knowledge_grok46.md` |
| F | Context → Thought Graph | Claude Opus 5 | standalone | `submissions/R0_F_extraction_opus5.md` |
| G | Benchmark / falsification | GPT-5.6 Sol MAX | standalone | `submissions/R0_G_benchmark_gpt56.md` |
| H | Architecture red team | Grok 4.6 xhigh | should not optimize to save the design | `submissions/R0_H_redteam_grok46.md` |

Model assignments are execution choices, not mission definitions. Anyone may reproduce a mission with another model or manually.

## Why B and C are duplicated

B and C are the algorithmic center of the first architecture:

```text
Thought Graph
  -> fingerprints / candidate retrieval     [B]
  -> structural verifier / alignment        [C]
```

If two different model families independently converge, that is useful evidence. If they disagree, the disagreement becomes a targeted architecture question rather than being averaged away.

## Recommended launch order

Launch all runs in parallel if possible. If compute/access is constrained, prioritize:

1. B1 + B2
2. C1 + C2
3. G
4. A + D + F
5. E + H

G is high priority because it defines the measurement instrument used to judge the other claims.

## Contribution / donated compute

If a friend or contributor wants to provide model access or tokens, ask them to run an **additional independent reproduction** rather than rerunning a broad generic prompt.

Examples:

- B3 with Grok
- C3 with another model or a human algorithm researcher
- G2 designed independently
- H2 by a deliberately skeptical human reviewer

Name the result according to `CONTRIBUTING.md` and state whether the contributor had seen existing submissions.

## Synthesis gate

Do not move directly from one compelling report into implementation.

After the primary submissions arrive:

1. compare B1 vs B2;
2. compare C1 vs C2;
3. extract constraints from A, D, E, F;
4. use G to define pass/fail tests;
5. use H to attack the resulting candidate architecture;
6. write a Decision Matrix;
7. write Invariance Specification;
8. write ADRs for retrieval and verification;
9. only then freeze Thought DNA v0.1.

## Public status convention

Each run may be tracked via a GitHub issue. Use issue comments for logistics, but preserve actual research artifacts as versioned Markdown in `research/submissions/`.

The repository, not a private chat transcript, is the durable record.