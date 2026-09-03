# R13B-RICH-RESULTS — run record

- mission: #90
- canonical agent: `dima2010-anthropic-fable5-7328` (Anthropic / Claude Fable 5)
- run_id: `R13B-RICH-RESULTS-F5`
- base: accepted main `a6074d1` (R13 live product merged)

## Canonical structured result

`resonance-rich-result/0.1` (`src/product/rich.py`, declared JSON Schema in
`RICH_RESULT_SCHEMA`) wraps the accepted R13 live payload without touching row
order or scores and adds exactly two per-row fields:

- `intro_state` — from the R12B-authoritative consent source
  (`available`/`unavailable`; `requested`/`accepted` are reserved in the enum
  for R14's durable intro records). No contact data exists anywhere in the
  pipeline.
- `ui_ref` — stable human-UI deep link (`/#match=<result_id>:<session_id>`).

`query_ref`, engine/contract `provenance`, `freshness`, the k-anonymous
`aggregation`, and the location disclaimer ride along unchanged.

## Deterministic visuals

Both renderers consume ONLY the authorized structured result — an image can
never contain more than the JSON the same viewer received:

- `render_map_svg` — equirectangular plot of consented match locations
  (pseudonym labels only; no ids of any kind) + the k-anonymous aggregation
  bars, all inputs sorted, no clocks/randomness. A pinned-sha256 regression
  guards the canonical seeded render.
- `render_structure_svg` — correspondence diagram from the row's own evidence
  block.

Byte-level leak scans (`ses-`/`person-`/`thought-`/`result-`/`token`) are
regressions on both renderers.

## Access model

Visuals are generated per request after full authorization: stored results are
subject-bound and generation-checked (`load_result_payload`), and every row is
**re-projected against current blocks/consent at read time**, so a block placed
after discovery (which moves no corpus generation) disappears from both the
rich JSON and the regenerated image, while a revoke invalidates the stored
result entirely (typed `stale_result`). HTTP visuals are served
`Cache-Control: private, no-store`; there are no long-lived or cross-identity
URLs by construction.

## MCP packaging

`to_mcp_content` returns the current MCP content model: `structuredContent`
(schema-declared), a text block that keeps image-less clients fully usable,
and `EmbeddedResource` SVG blocks when visuals are requested. R15 mounts this
from the remote server; the browser WebMCP surface keeps the page itself as the
visual (accepted R10 behavior) and shares byte-identical match rows via the
compat endpoints.

## Evidence commands

```
python3 -m unittest tests.test_product_rich -v
python3 -m unittest tests.test_product_http tests.test_product_live
python3 -m unittest discover -s tests
```
