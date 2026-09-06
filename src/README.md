# Source

Core implementation begins only after `R0-SYNTHESIS` is explicitly **ACCEPTED**. See `work/queue.yaml` for the live dependency chain.

The Resonance engine must remain independently callable without MCP. MCP is a thin transport adapter and is hard-blocked until `R5-INTEGRATION` is ACCEPTED.

Expected conceptual modules, refined by accepted R1 interfaces:

```text
graph/
interfaces/
extraction/
fingerprint/
index/
alignment/
scoring/
explanation/
mcp/
```

`src/fingerprint/` and `src/index/` implement R3 retrieval against the accepted
interfaces. They must not import alignment, scoring, extraction internals, or MCP.

The implementation sequence is operationally defined as:

```text
R1-SCHEMA
  -> R1-INTERFACES + R1-BENCHMARK
  -> R2-EXTRACTION + R3-RETRIEVAL + R4-VERIFIER
  -> R5-INTEGRATION
  -> R6-MCP
  -> R6-E2E
```

R2/R3/R4 should communicate only through the accepted public interfaces, not each other's internals. The rule that once named `src/mcp/` still holds and now applies to `src/product/`: **every protocol surface delegates to the accepted engine facade** rather than duplicating extraction, retrieval, verification or scoring logic. There is no `src/mcp/` — the stdio adapter was retired and the one `resonance_*` tool vocabulary lives in `src/product/mcp_bridge.py`, served to the browser and to chat clients alike.

`src/extraction/` implements R2: cue-grounded extraction plus a manual non-LLM ingest path through the same Thought DNA validator.

Mission-specific ownership and acceptance gates live under `engineering/missions/` and the linked GitHub Issues.