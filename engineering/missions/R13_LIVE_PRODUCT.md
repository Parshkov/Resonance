# R13-LIVE-PRODUCT — run record

- mission: #85
- canonical agent: `dima2010-anthropic-fable5-7328` (Anthropic / Claude Fable 5)
- run_id: `R13-LIVE-PRODUCT-F5`
- base: accepted main `1ab367b0` (R10/R11/R12/R12B/R12C all canonically accepted)

## What this run adds

`src/product/` — the live product boundary. Composition only:

| concern | provided by | product layer adds |
| --- | --- | --- |
| auth, ownership, CSRF/origin, limits | R12 + R12B | cookie session issuance over HTTP |
| prepare → preview → confirmed share | R12C | thin delegation (one boundary) |
| durable corpus, fail-closed discover | R11 | freshness surfaced on every response |
| discovery DTO, order, scores | R8 engine layers | pass-through, byte-order preserved |
| evidence read fidelity | R10 pattern | `result_id`-bound store, generation-checked |
| presentation privacy | R12B primitives | per-viewer block filtering, k-anonymous heat buckets, coarse distance context |

The product layer implements **no matching, scoring, or ranking** (regression-
enforced): it may only redact or drop rows that current consent or
viewer-relative blocks forbid — order and scores are never touched.

## Live vs seed

The server boots on the accepted R7 seed corpus as the ambient platform
baseline (`record_kind=synthetic`, honestly labeled); live user sessions are
`record_kind=volunteer`. `--no-seed` starts empty. Responses carry
`source: "live"` and `mode: "live"`; the deterministic replay demo remains the
separate, clearly labeled judging mode from R9/R10.

## Known limitation (disclosed, out of R13 scope)

Cold-start corpora of one or two near-duplicate sessions can be ranked out by
the accepted MULTI retrieval's discriminativeness weighting (the small-N /
tie-degeneracy behavior measured in the R5 qualified GO). The pilot always
ships with the seed baseline, which gives retrieval the distributional mass it
assumes; changing retrieval is out of scope for R13 by mission rule
("use accepted engine/retrieval... do not introduce vector/semantic
reranking").

## Freshness / consistency

Every discovery response and `/api/product/state` carries
`db_generation` / `serving_generation` / `index_current` / `engine_snapshot`.
Reads of stored results are refused (typed `stale_result`) once the durable
generation moves — the R10 fidelity rule generalized to the live store.

## Evidence commands

```
python3 -m unittest tests.test_product_live -v
python3 -m unittest tests.test_product_http -v
python3 -m unittest discover -s tests
python3 -m src.product.server --db live.sqlite3   # http://127.0.0.1:8788
```
