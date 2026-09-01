# Resonance MCP adapter — independent R6 repeat Q7V2

This package is a thin stdio transport over the accepted R5
`ResonanceEngine`. It owns no extraction, retrieval, alignment, scoring, or
benchmark logic. Every tool converts wire data to the accepted public graph or
engine types, calls the corresponding facade method, and serializes the typed
result.

The wire implementation is dependency-free and pins the current stable MCP
revision `2025-11-25`. It also negotiates `2025-06-18`, `2025-03-26`, and
`2024-11-05` for older stdio clients. Messages are UTF-8 JSON-RPC 2.0 objects,
one per line; stdout contains protocol messages only. This follows the official
[MCP lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle),
[tools contract](https://modelcontextprotocol.io/specification/2025-11-25/server/tools),
and [stdio transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports).

## Run

From the repository root, start a memory-only server:

```bash
python3 -m src.mcp.server
```

For durable local corpus/index state, provide a data directory:

```bash
python3 -m src.mcp.server --data-dir .resonance-state
```

`python3 -m src.mcp` is an equivalent entry point. A typical local-client
configuration is:

```json
{
  "mcpServers": {
    "resonance": {
      "command": "python3",
      "args": ["-m", "src.mcp.server", "--data-dir", ".resonance-state"],
      "cwd": "/absolute/path/to/Resonance"
    }
  }
}
```

Client configuration keys vary by host; the command and arguments above are
the transport contract.

## Tools

The catalog is deterministic and exposes exactly the mission's six operations.
Every tool has a closed `inputSchema` and `outputSchema` (`additionalProperties:
false` at owned object boundaries).

| Tool | Input | Engine delegation |
|---|---|---|
| `ingest_thought` | `context`, optional `source_id` | `EngineFacade.ingest` |
| `index_thought` | complete Thought DNA v0.1 object | `EngineFacade.index` |
| `find_resonance` | Thought DNA or `{ "id": ... }`, `mode`, optional `k` | `EngineFacade.find` |
| `compare_thoughts` | two Thought DNA objects/references and `mode` | `EngineFacade.compare` |
| `explain_resonance` | query/candidate thought IDs | `EngineFacade.explain` |
| `get_thought` | thought ID | `EngineFacade.get` |

`mode` is one of `structural`, `analogical`, or `complementary`; `k` is bounded
to 1–100 at the transport boundary. Manual Thought DNA follows the same
validator and engine path as extracted graphs. Compare/find call no LLM.

Successful calls return both MCP text content and identical
`structuredContent`. The structured envelope contains:

```text
operation
result
metadata
  adapter / engine / interface / schema / score-contract versions
  index and verifier config identities
  corpus snapshot and thought count
  persistence mode
```

Verifier results preserve the full score vector, node/relation/path mappings,
unmatched items, contradictions, explanations, source spans/manual provenance,
retrieval flags, and solver config. No scalar-only transport projection exists.

Tool-domain failures (invalid Thought DNA, unknown IDs, invalid modes, snapshot
integrity failures) are returned as MCP tool results with `isError: true` so a
client/model can correct them. Unknown tool names and malformed JSON-RPC remain
protocol errors.

## Persistence contract

Without `--data-dir`, the server is deliberately memory-only. With
`--data-dir`:

- startup accepts either an empty directory or one complete R5 snapshot
  (`manifest.json`, `store.json`, and `index.json`);
- partial, hash-mismatched, version-mismatched, config-forged, or
  store/index-divergent snapshots fail closed before serving;
- every successful `index_thought` writes the accepted manifest-bound R5
  snapshot; and
- a restart restores the thought store and candidate index exactly.

The R5 snapshot does not persist the process-local comparison explanation
cache. After restart, rerun `compare_thoughts` or `find_resonance` before
`explain_resonance`. This limitation is explicit rather than inventing a second
transport-only persistence format.

## Scope and known upstream evidence

This adapter does not compensate for the R5 acceptance record: frozen v0.1
retrieval Recall@5 remains `0.7272727`, all six gate vocabulary-substitution
pairs retain the accepted classification divergence, and the unevaluated gates
remain unevaluated. MCP exposes the accepted engine behavior; it does not
rerank, change thresholds, hide failures, or reinterpret benchmark gold.

The implementation supports stdio tools only. It does not implement HTTP,
resources, prompts, sampling, tasks, or remote authorization. A local data
directory should be protected with ordinary filesystem permissions; no
credentials belong in its snapshot or client configuration.

## Validation and provenance

Run the mission tests and the complete regression suite from the repository
root:

```bash
python3 -m unittest tests.test_mcp_repeat_q7v2 -v
python3 -m unittest discover -s tests -v
```

The mission test starts a real clean stdio subprocess, exercises lifecycle,
discovery, and a tool call, verifies manual-graph indexing/comparison,
restarts from a manifest snapshot, rejects tampered/partial snapshots, checks
structured evidence, and statically prevents transport imports of matching
component internals.

Public provenance: `parshkov-openai-gpt5-codex-q7v2`, OpenAI GPT-5 Codex
(exact runtime build not exposed), Codex environment, Python standard library,
run `R6-MCP-REPEAT-Q7V2`. Web use was limited to the official MCP specification
pages linked above; no additional agents were used.
