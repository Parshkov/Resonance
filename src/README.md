# Source

Core implementation begins only after `R0-SYNTHESIS` is explicitly **ACCEPTED**. See `work/queue.yaml` for the live dependency chain.

The Resonance engine must remain independently callable without MCP. MCP is a thin transport adapter and is hard-blocked until `R5-INTEGRATION` is ACCEPTED.

Expected conceptual modules, refined by accepted R1 interfaces:

```text
graph/
extraction/
fingerprint/
index/
alignment/
scoring/
explanation/
mcp/
```

The implementation sequence is operationally defined as:

```text
R1-SCHEMA
  -> R1-INTERFACES + R1-BENCHMARK
  -> R2-EXTRACTION + R3-RETRIEVAL + R4-VERIFIER
  -> R5-INTEGRATION
  -> R6-MCP
  -> R6-E2E
```

R2/R3/R4 should communicate only through the accepted public interfaces, not each other's internals. `src/mcp/` must delegate to the accepted engine facade rather than duplicating extraction, retrieval, verification or scoring logic.

Mission-specific ownership and acceptance gates live under `engineering/missions/` and the linked GitHub Issues.