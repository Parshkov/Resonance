# R0-B — Relational Constellation Fingerprinting

Read `research/R0_MASTER_BRIEF.md` and `research/MISSION_CONTRACT.md` first.

## Decision question

Can Resonance use a Shazam-like sparse fingerprinting layer to retrieve candidate Thought Graphs extremely cheaply while remaining robust to paraphrase, noise, partial graphs, and moderate structural edits?

The goal is **not** full graph comparison. The goal is candidate retrieval.

## Investigate

- Shazam landmark/hash principles
- graphlets and motif hashing
- Weisfeiler-Lehman refinement / subtree kernels
- neighborhood hashing
- locality-sensitive hashing where relevant
- MinHash / set similarity where relevant
- structural graph fingerprints
- inverted indexes and entropy/commonness filtering

## Central problem

Identify the Thought-Graph analogue of a robust Shazam landmark pair or constellation.

Possible ingredients include node roles, relation types, direction, graph distance, local topology, semantic buckets, and knowledge anchors, but do not assume this combination is correct.

## Resolve

1. What is a robust Cognitive Landmark?
2. What exactly is a Relational Fingerprint?
3. What fields are discretized/hashed and which remain continuous?
4. How many candidate fingerprints should a ~50-node Thought produce?
5. How are rare/high-information fingerprints selected?
6. How are generic motifs prevented from creating huge false-positive lists?
7. Which transformations can the fingerprint realistically survive?
8. What index should be used for a corpus of ~1M Thoughts?
9. What is the graph analogue of Shazam's "many hashes agree on one time offset" consistency test?
10. What requirements does this impose on Thought DNA?

## Required artifact

Propose at least one concrete fingerprint record, for example in pseudocode/JSON form, and describe the exact retrieval query and candidate-voting process.

This mission is run independently as B1 and B2. Do not inspect the sibling report before submitting.