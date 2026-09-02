# R6-E2E — clean-client MCP demo

A stdlib-only MCP client talks to the accepted Resonance stdio server. It does
not import `src.engine`, `src.mcp`, or any matching internals. All five
acceptance scenarios use frozen Benchmark v0.1 Thought DNA documents as JSON.

## Run

From the repository root (Python ≥ 3.10, no extra packages):

```bash
python3 demo/run.py
```

This launches `python3 -m src.mcp.server`, performs MCP `initialize` / `ping` /
`tools/list`, then `compare_thoughts` (and one `find_resonance`) over NDJSON.
It writes `demo/report.json` and `demo/transcript.jsonl`.

```bash
python3 -m src.mcp.server          # optional: speak the wire yourself
```

Framing is newline-delimited JSON-RPC 2.0 (MCP 2024-11-05). Do not send
LSP-style `Content-Length` headers.

## Scenarios

Pinned in `scenarios.json` against `benchmark/r0-v0.1/graphs.jsonl`
(`sha256 b749f10e4178a5b21a9bab03f01defbbb35f2688faa8103b952135c63ee1c9cd`):

| id | case | expected |
|---|---|---|
| S1 | C01-Q vs C01-C10 structural | `negative` (same words, structural_score < 0.85) |
| S2 | C01-Q vs C01-C09 analogical | `analogical` with mapping + find hit |
| S3a | C01-Q vs C01-C04 structural | `approximate` (containment > symmetric) |
| S3b | C01-Q vs C01-C05 structural | `approximate` with R_path > 0 |
| S4 | C01-Q vs C01-C16 complementary | `complementary` with directional K_comp |
| S5 | G01-Q vs G01-C10 structural | `negative`, hard_rejection, H_sign_conflict |
| U1 | mode=`semantic` | engine-stage `isError` (unsupported mode) |
| T1 | unknown JSON-RPC method | transport `-32601` |

Results must carry the accepted identity:

```
adapter_version:        resonance-mcp/0.1
engine_version:         resonance-engine/0.1
interface_version:      resonance-interfaces/0.1
verifier_config_hash:   3e107bc4850537730949d013ffa0f335b3ddbf9b0d64bb640fe34f893dbb1b1d
```

This is the first working Resonance MCP milestone. It is not a corpus-scale or
production claim. Retrieval recall on the full frozen v0.1 gate remains the
R5-recorded 0.727 failure; this demo does not rerank or compensate.

## R7 corpus

`demo/corpus/` is the consented multi-session demo corpus. It wraps accepted
Thought DNA with consent/presentation metadata and does not implement
retrieval, alignment, or scoring. See `demo/corpus/README.md`.

## R9 visual client

`demo/ui/` is the presentation-only, competition-recordable discovery client.
It supports deterministic REPLAY from the accepted R8 fixture and LIVE through
the accepted `discover_resonance` MCP path, both pinned to `analogical / k=15`.
See [`ui/README.md`](ui/README.md) for launch, recording, privacy, and
validation instructions.
