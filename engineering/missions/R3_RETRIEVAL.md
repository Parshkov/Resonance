# R3-RETRIEVAL — Multi-channel candidate generation

Issue: #41

## Objective
Implement fast candidate generation with a structural channel plus separate content/Knowledge DNA channels.

## Prerequisites
R0-SYNTHESIS, R1-SCHEMA and R1-INTERFACES ACCEPTED. R1-BENCHMARK is the promotion gate.

## Ownership
`src/fingerprint/`, `src/index/`, retrieval persistence and retrieval tests. Do not implement final verifier decisions.

## Required outputs
- multi-scale D0+D1 landmark descriptors
- typed/directed path fingerprints and distance buckets
- DF/IDF/commonness suppression
- inverted structural index
- correspondence-consensus voting + seed correspondences
- separate content/Knowledge retrieval evidence
- deterministic index/config versions, persistence and scale instrumentation
- E1 reproduction

## Acceptance
Use issue #41 and accepted synthesis/R0-G gates. Retrieval must flag polarity as unverified. Role-only structural keys are not the shipped default. Per-channel evidence and postings/latency must remain observable.