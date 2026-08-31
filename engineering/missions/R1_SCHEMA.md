# R1-SCHEMA — Executable Thought DNA v0.1

Issue: #38

## Objective
Implement the accepted Thought DNA v0.1 as executable schemas, typed models, canonical serialization and validators.

## Prerequisite
R0-SYNTHESIS ACCEPTED.

## Ownership
Primary: `src/graph/`, schema files, schema tests, canonical fixture examples. Do not implement extraction/retrieval/alignment/MCP.

## Required outputs
- JSON Schema and Python model/API
- deterministic canonical serialization
- stable graph/node/edge IDs
- role, relation direction/type, polarity/modality, confidence, provenance/source-span, atomic/granularity and Knowledge DNA fields
- valid/invalid fixtures and migration/version rules

## Acceptance
Use the exact gate in issue #38. Demonstrate deterministic permutation-invariant serialization and round-trip preservation. Reject missing/invalid polarity, direction, provenance and version fields when required.