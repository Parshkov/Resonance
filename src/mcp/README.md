# R6 — MCP transport over the accepted Resonance engine

A thin newline-delimited JSON-RPC 2.0 stdio server (MCP protocol
`2024-11-05`), stdlib-only. Handlers parse arguments, call the accepted
`EngineFacade`, and serialize frozen-interface results — no retrieval,
alignment, scoring, extraction, or benchmark logic lives here (engineering
contract §7; enforced by a source-scan test).

```bash
python3 -m src.mcp.server                    # fresh engine
python3 -m src.mcp.server --snapshot DIR     # from a manifest-verified snapshot
```

## Tools

The six required operations map 1:1 to `EngineFacade`:
`ingest_thought` → `ingest` · `index_thought` → `index` · `find_resonance` →
`find` · `compare_thoughts` → `compare` · `explain_resonance` → `explain` ·
`get_thought` → `get`. Two explicit persistence tools go beyond the minimum:
`save_snapshot` / `load_snapshot` wrap the engine's ONE manifest-verified
snapshot (`load` fails closed on any integrity mismatch, surfaced as a tool
error with the engine's own message).

Every response carries `metadata`: adapter/engine/interface versions, the
verifier `config_hash`, and the index `corpus_snapshot`. VerifierResults are
serialized whole — score vector (`ScoreVector.to_wire()`), mapping, matched
relations and guarded paths, unmatched items, contradictions, the full
explanation, and per-item span provenance.

Manual Thought DNA (`provenance.kind=manual`) indexes and compares through
the same validator with no LLM anywhere. Engine-declared failures (unknown
mode via `require_mode`, Thought DNA validation, `EngineIntegrityError`)
return `isError: true` with the engine's message; transport-level problems
use JSON-RPC error codes. The engine itself remains import-independent of
this package (subprocess-attributed test on the engine side).
