# R0-D — Multiscale and Granularity Invariance

Read `research/R0_MASTER_BRIEF.md` and `research/MISSION_CONTRACT.md` first.

## Decision question

How should Resonance recognize the same reasoning when one Thought Graph is coarse and another expands the same relation through intermediate nodes or nested branches?

Example:

```text
A -> B
```

versus

```text
A -> X -> Y -> B
```

## Investigate where useful

- WL signatures at multiple radii
- graph diffusion
- heat kernels / heat-kernel signatures
- diffusion distances
- spectral signatures
- graph coarsening / contraction
- hierarchical graph representations
- persistent homology / topological summaries

## Resolve

1. What is the simplest method that gives useful granularity robustness within the sprint?
2. Should scale invariance live primarily in preprocessing, fingerprints, verifier, or a combination?
3. How should low-information intermediate nodes be contracted without destroying meaningful causal structure?
4. What multiscale signature, if any, is cheap enough for retrieval?
5. Which scale transformations cannot reasonably be treated as invariant?
6. What fields must Thought DNA preserve to allow safe coarsening or multiscale comparison?
7. Give a <=2-hour experiment that compares the proposed method against a no-multiscale baseline.

Do not select mathematically sophisticated machinery merely because it is elegant. Prefer the cheapest mechanism that demonstrably improves the benchmark.