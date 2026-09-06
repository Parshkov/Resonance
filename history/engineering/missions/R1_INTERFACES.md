# R1-INTERFACES — Freeze engine module boundaries

Issue: #46

## Objective
Define the minimal typed Python boundaries that allow extraction, retrieval, verification, scoring/explanation and persistence to be implemented independently.

## Prerequisites
R0-SYNTHESIS ACCEPTED. Coordinate with R1-SCHEMA; accepted Thought DNA types are authoritative.

## Ownership
Public protocols/interfaces, facade types, fakes/stubs and import-boundary tests. Do not implement mission algorithms.

## Required outputs
- validation/canonicalization interface
- extraction result interface
- index/update/query and candidate interfaces
- verifier result interface
- score/explanation payload interface
- store interface
- engine/config/schema version identifiers across boundaries
- fake end-to-end flow proving contracts compose

## Acceptance
Use issue #46. R2/R3/R4 must be able to implement without importing each other's internals. Core interfaces contain no MCP transport types.