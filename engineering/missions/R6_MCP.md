# R6-MCP — Thin MCP adapter

Issue: #44

## Objective
Expose the accepted R5 Resonance engine through MCP without moving engine logic into transport handlers.

## Prerequisite
R5-INTEGRATION ACCEPTED. This is a hard block.

## Ownership
`src/mcp/`, MCP packaging/config and transport tests. Core engine modules remain independently runnable.

## Required operations
- `ingest_thought(context)`
- `index_thought(thought)`
- `find_resonance(thought, mode, k)`
- `compare_thoughts(a, b, mode)`
- `explain_resonance(a, b)`
- `get_thought(id)`

## Acceptance
Use issue #44. Tool schemas map directly to accepted engine interfaces; no retrieval/alignment/scoring logic lives only in handlers. Manual Thought DNA works without an LLM. Responses include mappings/explanations/provenance and version/config metadata. Persistence behavior is explicit and tested.