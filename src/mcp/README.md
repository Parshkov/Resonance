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
the same validator with no LLM anywhere.

**Documented coupling beyond the frozen protocol (review N3):** `metadata()`
reads `engine.verifier.config_hash` and `engine.candidate_index
.corpus_snapshot`, and the snapshot tools call `ResonanceEngine.dump/load` —
concrete accepted-engine APIs, not `EngineFacade` methods (the frozen facade
exposes no config/snapshot/persistence surface, while the mission requires
version/config metadata). R6-E2E must not treat these attributes as a public
transport contract. **Framing (N5):** stdio is newline-delimited JSON only,
per MCP 2024-11-05 — clients must not assume LSP-style Content-Length
headers. `ping` replies `{}`. Engine-declared failures (unknown
mode via `require_mode`, Thought DNA validation, `EngineIntegrityError`) and
filesystem failures on the persistence tools (missing/unreadable snapshot
directory) return `isError: true` with the underlying message; any other
unexpected handler exception maps to JSON-RPC `-32603` — one bad `tools/call`
can never terminate the stdio session (regression-tested: the stream keeps
answering `tools/list`/`ping` afterwards). The engine itself remains import-independent of
this package (subprocess-attributed test on the engine side).
