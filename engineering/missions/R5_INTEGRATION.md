# R5-INTEGRATION — End-to-end engine gate before MCP

Issue: #43

## Objective
Integrate the accepted modules into a normal Python engine and make a GO/NO-GO decision for opening the MCP mission.

## Prerequisites
R1-SCHEMA, R1-INTERFACES, R1-BENCHMARK, R2-EXTRACTION, R3-RETRIEVAL and R4-VERIFIER ACCEPTED.

## Ownership
Engine facade/orchestration, local persistence composition, integration tests and benchmark report. Do not add MCP transport.

## Required path
`context/manual graph -> Thought DNA -> validate/canonicalize -> index -> retrieve -> verify -> score -> explain`

## Acceptance
Use issue #43. The full engine must run with MCP absent. Run frozen Benchmark v0.1 with stage-attributed failures and preserve every non-compensating failure. Required demos include lexical hard negative, cross-domain analogy, partial/granularity, polarity/causal contradiction, and complementarity if v0.1 claims it.

R6-MCP stays BLOCKED until this mission is explicitly ACCEPTED.