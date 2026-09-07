# Resonance — Research Sprint R0 Agent Missions

Each agent receives `research/R0_MASTER_BRIEF.md` plus exactly one mission below.

Run duplicate missions independently; do not show one model the other model's answer.

Recommended filenames for returned reports:

```text
01_structure_mapping.md
02_fingerprinting.md
02b_fingerprinting_independent.md
03_alignment.md
03b_alignment_independent.md
04_multiscale.md
05_knowledge.md
06_extraction.md
07_benchmark.md
08_redteam.md
```

---

## Mission A — Structure Mapping and Human Analogy

Determine what mathematical / representational properties a Thought Graph must preserve if Resonance is intended to detect human-recognizable structural analogies.

Research especially:

- Structure-Mapping Theory
- Structure-Mapping Engine (SME)
- MAC/FAC
- systematicity
- one-to-one correspondence constraints
- relational consistency
- higher-order relations
- causal analogy
- relational vs attribute similarity

Resolve:

1. Which ideas from SME remain useful for Resonance?
2. What does SME require from the representation?
3. Are ordinary binary graph edges enough?
4. Do relations themselves need to become nodes/objects?
5. What is the smallest usable version of structure mapping we could implement?
6. What should we absolutely not reproduce from classical SME?
7. How can relational analogy be scored separately from semantic similarity?

The final report must make a concrete recommendation for the relational semantics of Thought DNA.

---

## Mission B — Relational Constellation Fingerprinting

Investigate whether we can build a Shazam-like retrieval system for Thought Graphs.

The goal is not full graph comparison. The goal is to generate sparse, robust, high-information fingerprints from small local graph structures so candidate analogous graphs can be retrieved extremely cheaply.

Research where relevant:

- Shazam landmark/hash principles
- graphlets
- Weisfeiler-Lehman refinement
- WL subtree kernels
- neighborhood hashing
- locality-sensitive hashing
- MinHash / set similarity
- motif hashing
- structural graph fingerprints
- inverted indexes

Central question:

> What is the Thought-Graph analogue of Shazam's robust landmark pair?

Consider fingerprints derived from node roles, relation types, direction, graph distance, local topology, semantic buckets and knowledge anchors — but do not assume this is correct.

Resolve:

1. What constitutes a robust Cognitive Landmark?
2. What constitutes a Relational Fingerprint?
3. How many fingerprints might a 50-node Thought produce?
4. How should rare/high-information fingerprints be selected?
5. How do we prevent common motifs from generating enormous false-positive lists?
6. Can fingerprints survive paraphrase and moderate graph edits?
7. What would the inverted index look like?
8. What becomes the equivalent of Shazam's “many matches agreeing on one time offset” for graph correspondence?

Produce a concrete fingerprint format implementable immediately.

---

## Mission C — Approximate Graph Alignment

Find the best practical algorithm for expensive verification after candidate retrieval.

Given two Thought Graphs of roughly 10–100 nodes, determine:

- whether they contain structurally analogous subgraphs,
- which nodes correspond,
- which relations correspond,
- how strong that alignment is.

Investigate where relevant:

- Graph Edit Distance
- maximum common subgraph
- subgraph isomorphism
- approximate graph matching
- quadratic assignment
- optimal transport
- Gromov-Wasserstein
- Fused Gromov-Wasserstein
- spectral graph matching
- SME-style constraint matching
- hybrid methods

Critical requirements:

- graphs may have different sizes
- labels may differ
- semantic node similarity is soft
- structure matters strongly
- partial matching matters
- output must include actual alignment, not only a scalar score
- <=20 expensive comparisons per query is acceptable

Recommend one primary verifier and one fallback.

Also determine whether a hybrid pipeline such as:

```text
soft correspondence
→ structural consistency
→ discrete mapping
```

is preferable to one monolithic algorithm.

Give an implementable Resonance scoring equation.

---

## Mission D — Multiscale and Granularity Invariance

Solve this specific problem:

The same idea may appear as:

```text
A → B
```

or:

```text
A → X → Y → B
```

or as a nested branch. Resonance should still detect structural correspondence.

Research practical methods where useful:

- WL at different radii
- graph diffusion
- heat kernels / heat kernel signatures
- diffusion distances
- spectral signatures
- graph coarsening
- hierarchical graph representations
- persistent homology / topological summaries

Do not recommend sophisticated mathematics merely because it is elegant.

Determine whether scale invariance should come from:

A. preprocessing / graph contraction,
B. multiscale fingerprints,
C. verifier,
D. a combination.

Give the simplest practical algorithm and thresholds we can test in this MVP.

---

## Mission E — External Knowledge Space

Investigate how external knowledge requirements can serve as an independent resonance signal.

Hypothesis:

Two Thought branches may be strongly related if solving them requires substantially overlapping knowledge, even when their wording differs.

We do not want to build a universal ontology during the MVP.

Investigate possible anchors such as:

- Wikidata
- Wikipedia concept graph
- ACM Computing Classification System
- OpenAlex concepts/topics
- domain taxonomies
- prerequisite graphs
- ontology embeddings if useful

Resolve:

1. What should a Thought node point to?
2. How should “knowledge required to solve this node” differ from “what this node is about”?
3. How can knowledge overlap be scored?
4. How can nearby but non-identical concepts be compared?
5. Where do books, papers, courses and experts fit?
6. Can knowledge anchors improve cross-domain analogy, or only same-domain matching?
7. What is feasible without building a large KG ingestion pipeline?

Propose Knowledge DNA v0.1 with a minimal interface suitable for the MVP.

---

## Mission F — Context to Thought Graph

Design the transformation:

```text
unstructured human text/context
→ canonical Thought Graph
```

LLMs are allowed here. The comparison engine itself should not depend on an LLM, so extraction quality and normalization matter greatly.

Resolve:

1. What information can an LLM reliably extract?
2. Which graph distinctions are too unstable to trust?
3. What minimal node taxonomy is reliably extractable?
4. What minimal edge taxonomy is reliably extractable?
5. Should causal, prerequisite, supports, contradicts, part-of, goal and constraint edges be separate?
6. How should uncertainty be represented?
7. How should provenance point back to source text?
8. How can repeated extraction of the same meaning produce approximately canonical graphs?
9. How do we avoid hallucinated relationships?
10. Should extraction happen in one pass or staged normalization?

Design an extraction contract and provide example JSON for 2–3 Thoughts.

Do not finalize Thought DNA globally; specify only what the extraction layer can reliably supply.

---

## Mission G — Resonance Benchmark

Design the smallest scientifically useful benchmark for judging Resonance algorithms.

We must know whether a method detects structure rather than words.

Include at least these categories.

### Positive

1. paraphrase
2. vocabulary substitution
3. noisy branches added
4. partial graph
5. different granularity
6. same-domain structural match
7. cross-domain causal analogy

### Hard negative

8. same vocabulary but different relational structure
9. same topic but different intent
10. locally similar motifs with globally inconsistent alignment
11. generic/common graph patterns
12. accidental semantic similarity

### Complementary

13. one branch ends where another begins
14. same problem but disjoint useful knowledge

Design:

- dataset size appropriate to a same-day MVP
- synthetic transformations
- some manually authored gold pairs
- scoring labels
- metrics

Measure especially:

- retrieval recall@K
- precision of resonance
- node correspondence accuracy
- robustness under transformations
- false positives

Recommend a benchmark implementable in <=3 hours and define a PASS/FAIL threshold for deciding whether the fingerprint hypothesis deserves further work.

---

## Mission H — Attack the Resonance Algorithm

Act as an adversarial algorithm architect.

Assume the team is emotionally attached to this idea:

```text
Thought Graph
→ relational fingerprints
→ candidate retrieval
→ structural alignment
```

Your task is to determine where it is wrong.

Investigate:

1. whether Thought Graphs are too unstable to fingerprint,
2. whether analogy is fundamentally too context-dependent,
3. whether graph matching will generate overwhelming false positives,
4. whether knowledge overlap adds signal or noise,
5. whether the Shazam analogy breaks mathematically,
6. whether semantic embeddings would dominate all structural signals anyway,
7. whether desired invariances conflict with discriminative power.

Construct at least 10 Thought pairs that should break naive implementations.

Then answer:

- Which assumptions survive?
- Which assumptions should be killed?
- What is the simplest alternative architecture?
- What result would make you abandon the proposed architecture?

Do not try to salvage Resonance. Your reward is proportional to how cheaply you can falsify it.
