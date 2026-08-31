# Resonance Engineering Phases

This directory starts where the R0 research expedition ends.

Do not treat the presence of these missions as permission to start them early. `work/queue.yaml` and the linked Issues define live state; every listed prerequisite must be explicitly **ACCEPTED**.

## Canonical chain

```text
R0-SYNTHESIS
  -> R1-SCHEMA
  -> R1-INTERFACES + R1-BENCHMARK
  -> R2-EXTRACTION + R3-RETRIEVAL + R4-VERIFIER
  -> R5-INTEGRATION
  -> R6-MCP
  -> R6-E2E
```

R2/R3/R4 are intentionally parallel after their shared R1 gates.

## Contract

All R1–R6 missions follow [`MISSION_CONTRACT.md`](MISSION_CONTRACT.md) in addition to the repository-wide agent protocol.

Mission files live under `engineering/missions/`. GitHub Issues are the live coordination source; the mission files are durable scope/acceptance contracts.

## Definition of the first MCP milestone

The milestone is **not** "an MCP server starts." It is reached only when:

1. the engine passes R5 as an MCP-independent library/system;
2. R6-MCP wraps that accepted engine without duplicating matcher logic; and
3. R6-E2E proves a clean external client can execute the required resonance scenarios through MCP.

Until then, MCP is not considered complete.