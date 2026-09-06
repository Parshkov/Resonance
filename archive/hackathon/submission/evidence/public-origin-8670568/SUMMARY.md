# Deployment evidence — public origin @ `8670568` (engine 0.2, local-workstation run)

- **Commit under test:** `8670568e174f63567d489c901817e3c575f5b5c2` (`main`, squash of #170 on top of
  #171 `d819d07` and #169 `fe5125f`, themselves on `0ee5dbe`)
- **Origin:** https://resonance-production-cfe3.up.railway.app · **MCP:** …/mcp
- **Railway:** project `670bcce5-…`, service `resonance` `172aa183-…`, environment `production` `da338ecd-…`
- **Deployment:** `d05c733f-283c-4016-8cf8-ce951270a99b` — SUCCESS 22:46:48Z, `commitHash 8670568e…`,
  branch `main` (auto-deploy). Earlier the same evening: `22c6c14d` (`8670568`, before the origin
  variables changed), `ae8e14f0` (`d819d07`), `7506c8de` (`fe5125f`).
- **Method:** run from the **sponsor's own macOS workstation**, not a cloud container. That is what
  makes this set different from `public-origin-0aea577`: a real Google Chrome install and direct
  public HTTPS egress, so Card A could finally run against a browser that has WebMCP.
  No tokens, codes or raw text recorded; pseudonyms, ids, scores and structure only
  (`grep` for token/bearer/JWT/DSN patterns over this directory returns nothing but the
  `verifier_config_hash`, `engine_snapshot` and benchmark fixture hashes).

## The headline: Card A is no longer unclaimed

**Native `document.modelContext` works, and Chrome Canary was never needed.**

Google Chrome **152.0.7977.83 stable**, launched with **`--enable-features=WebMCP`**, exposes
`document.modelContext`. Measured both ways on this machine: `typeof document.modelContext` is
`"undefined"` without the flag and `"object"` with it; the shipped binary contains `kWebMCP` and
`"Enables the WebMCP API."`. `navigator.modelContext` remains absent.

`submission/evidence/browser_harness.py` now runs the tools through that surface instead of a shim
and reports which mode produced the evidence. This run: **`mode: NATIVE`, 24/24 checks passed.**

| Card A step | native result |
|---|---|
| 1 — page renders, pills | app shell renders; header `Private · not discoverable`; capability pill not `unavailable` |
| 2 — tools listed in the browser's own surface | `document.modelContext.getTools({})` → **17 tools**, including all six R10 names plus the collaboration/workspace tools; `resonance_discover` carries `inputSchema` and `origin: https://resonance-production-cfe3.up.railway.app` |
| 3 — discover before sharing | fails closed, 409 `share_required` |
| 4 — `resonance_prepare_thought` | `discoverable: false`, `ses-5780be348626641a` |
| 5 — `resonance_get_share_preview` | `confirmation_token` returned; 10 nodes, 10 relations |
| 6 — `resonance_share_prepared_thought` (confirm) | `discoverable: true`; header flips to `Shared with Resonance`; pill `WebMCP · LIVE shared` |
| 7 — `resonance_discover` | `result-50e99c41372859f7d16b5de3`, `source: live`, 6 matches |
| 8 — `resonance_get_match` | evidence block returned |
| 9 — `resonance_update_consent(shared:false)` | `revoked: true`; LIVE discover and the old `result_id` both fail closed again |

Everything was invoked through `executeTool(tool, argsJsonString, {})` — the browser's own
invocation path — not by calling the page's `execute` function directly.

### The native API, as measured

Worth recording because it is what the harness had to be written against:

```
document.modelContext instanceof ModelContext
prototype: registerTool, getTools, executeTool, ontoolchange
getTools({})  -> Promise<Array>; entries own {name, title, description,
                 inputSchema, origin, window}
executeTool(tool, argsJsonString, {}) -> Promise<string>  (the tool result as JSON)
the page's own execute() receives the PARSED object
passing an object instead of a JSON string rejects:
  "UnknownError: Failed to parse input arguments"
```

**Honest limitation of the native surface.** When a tool fails closed, Chrome wraps the error:
the caller sees `UnknownError: Tool was executed but the invocation failed…`, not the product's
`share_required` code. The product still refuses correctly, and the page still shows the right
state, but an agent driving the browser natively does **not** receive the structured error the
remote-MCP path gives it. That is a property of the browser's WebMCP surface today, not of
Resonance, and nothing here should be read as claiming otherwise.

### The `cards > 0` check, made precise — and it passes for the right reason

`RELEASE_FREEZE_CHECKLIST.md` §13 recorded `cards > 0` after a LIVE discover as an imprecise
expectation. The exact rule is the renderer's: the rail shows `selectPrimaryMatches(payload)` —
discoverable matches with no `hard_rejection` and `mode_classification != "negative"`, capped at 4.

Measured this run:

```
cards=0  expected=0  from 6 returned  (0 eligible; classifications=['negative'])
data-state='empty'   shown-count='00 shown'
response-summary='6 returned · 0 resonances · 0 rejected'
```

Every live match for the page's own thought is `negative`, so an empty rail is the correct
fail-closed answer, and the harness now says so instead of going red. The old assertion would have
failed here — as it did on `0aea577` (16/18) — for behaviour that is right.

## Repository gates (on `8670568` + the purge tool)

| gate | result |
|---|---|
| `python3 -m unittest discover -s tests` | **467 tests OK, 2 skipped** (357 s). 464 on `0ee5dbe`; +3 from this work (the fixture-persona landing test, the capability-pill test, the canonical-origin test) and +1 more once the purge tool lands. The two skips need a local PostgreSQL. |
| `python3 benchmark/r0-v0.2/runner.py` | `overall_status: pass`, exit 0 — `benchmark_r0_v0.2.json` |
| `python3 benchmark/extraction-v0.2/runner.py` | `overall_status: pass`, exit 0 — `benchmark_extraction_v0.2.json` |

r0-v0.2 gate values unchanged: classification accuracy 1.0, polarity rejection 1.0, negative FPR
0.0, positive node F1 0.8469, Recall@5 1.0, Recall@20 1.0. **Benchmark gold was not edited** and
still awaits human review (ADR-0004).

## Public-origin acceptance

| # | check | result | artefact |
|---|---|---|---|
| P1 | `GET /api/product/health` | `ok: true`, `mode: live`, `index_current: true`; `resonance-engine/0.2`, extractor `0.2.0`, `verifier_config_hash 12998d45…`; `corpus.demo_personas_present: false`, `demo_sessions: 0`, `volunteer 62` | `health.json` |
| P2 | `ops/hosted_onboarding_probe.py --smoke --refresh --revoke --json` | **ONBOARDING PASS: 9/9 required**; smoke share `ses-417f5cf492d0c25d` revoked at the end | `hosted_onboarding_probe.{json,txt}` |
| P3 | `ops/oauth_smoke.py <origin>/mcp --auto-consent` | **27/27** | `oauth_smoke.txt` |
| P4 | `submission/evidence/abc_mcp_test.py <origin>/mcp` | **36/36**; all three guest sessions revoked, `still_discoverable=[]` | `abc.{json,txt}` |
| P5 | Card A — `browser_harness.py`, **real Chrome 152 with `--enable-features=WebMCP`** | **24/24, `mode: NATIVE`** | `card-a-browser/` incl. 5 screenshots |
| P6 | R9 empty/error state — `r9_empty_state_harness.py` | **18/18** (was 16/16; two new checks) | `r9_empty_state.{json,png}` |

### An environment note, so nobody mistakes it for a product failure

`ops/oauth_smoke.py` first failed with `SSL: CERTIFICATE_VERIFY_FAILED`. That is this workstation's
python.org Python 3.12 having no CA bundle configured — `curl` against the same URL succeeded
throughout. Re-run with `SSL_CERT_FILE` pointed at a `certifi` bundle: 27/27. Nothing on the origin
changed between the two runs.

## What this run fixed on the live product

A first-time visitor to the production origin used to see four invented people — Kwame A.
(Nairobi), Noah R. (Berlin), Mei L. (Austin), Gabe S. — each at structural 1.0000, before doing
anything, because `/api/config` served `default_source: "replay"`. `demo_personas_present: false`
was true of the database and not of the page. Fixed in #169 and verified on the deployed origin:

```
GET /api/config                 -> {"default_source": "live", "live_product": true}
GET /api/context                -> 409 share_required
GET /api/discover?source=live   -> 409 share_required
GET /api/context?source=replay  -> 200   (replay still reachable, now labelled
                                          "example personas, not real participants")
```

and in a real browser on the live origin: `data-state="unshared"`, 0 match cards, contradiction card
computed `display: none`, no persona or fixture-thought text anywhere in the rendered page.

Two further defects found and fixed in the same PR:

- `#contradiction-card` was `hidden` in JS but still on screen — `.contradiction-card { display: grid }`
  beat the browser default for `[hidden]`, so "Loading rejected results… / 0 REJECTED" survived into
  the empty, error and unshared states. `r9_empty_state_harness.py` asserted the `hidden` *property*,
  which is exactly why it shipped green; that harness now asks `getComputedStyle` instead.
- The WebMCP pill reported **consent** instead of **capability**: a browser with no
  `document.modelContext` showed `WebMCP · private`, byte-identical to one where registration
  succeeded. Card A step 1 asks a tester to stop on `unavailable`, so the signal had to come back.
  `RELEASE_MANIFEST.md` §4 said stock Chrome shows `WebMCP · unavailable` "by design"; as deployed
  before this run, it did not.

## Corpus hygiene — measured, tooled, not yet executed on production

The ten duplicate guest sessions listed in `public-origin-0aea577/SUMMARY.md` are **still present**.
This run measured what they cost, on the live corpus, in the A/B/C acceptance:

```
[PASS] A (retry storm) found by B (panic buying) — rank=4 score=1.0
[PASS] A ranks above C (structure beats shared vocabulary) — rank_A=4 rank_C=11 score_C=0.177
```

The genuine cross-domain analogy — the result the product exists to demonstrate — is at **rank 4**,
behind three exact copies of the query's own thought, each at structural 1.0. Unchanged from the
`9a79eb8` observation. The duplicates are not neutral clutter.

Why they were still there: `purge-demo` selects by `record_kind != "volunteer"` and these are real
`volunteer` rows, and the product's `delete_session` needs the *owner's* access token, which for
these long-gone guests no longer exists. `RESONANCE_PURGE_SESSIONS=<id>[,<id>…]` (#172) closes that
gap: it tombstones exactly the ids an operator types, through the accepted persistence API, with a
`session.delete` audit event per row, reporting `deleted` / `already_deleted` / `missing` for every
id so a typo is visible rather than silent.

**The production run has not happened.** It is: deploy #172 → set the variable with the ten ids
(**keeping `ses-a95528cc2a90ef11` and `ses-099c77441b96db62`, the A/A' pair**) → redeploy → check
the log line and `/api/product/health` → unset the variable → re-run `abc_mcp_test.py` and record
the new rank **whichever way it goes**, including if the analogy does not rise.

This run created guest sessions (Card A, the onboarding smoke, three A/B/C identities) and **revoked
every one of them**: `still_discoverable=[]` in `abc.json`, `revoked=True discoverable=False` in the
onboarding probe, and Card A's `resonance_update_consent(shared:false)` → `revoked: true`. Nothing
here adds to the duplicate problem.

## Deviations

- Card A ran against the platform origin, not `resonance.parshkov.com`: at the time of the run the
  custom domain's certificate was still `VALIDATING_OWNERSHIP`, so the new host did not serve TLS.
  DNS is correct and propagated (`CNAME resonance.parshkov.com -> ositddso.up.railway.app`, no CAA
  restrictions).
- Cards B, C and D remain **UNEXECUTED** in this run and must not be claimed. Card C additionally
  needs a ChatGPT Business/Enterprise/Edu workspace. Grok is now known to support custom remote MCP
  connectors (`grok.com/connectors` → New Connector → Custom), so a Card-B-equivalent run there is
  possible and is also unexecuted.
- `RESONANCE_DB` and `RESONANCE_CONFIRMATION_SECRET` were neither read nor modified.
  `RESONANCE_SEED_DEMO` was never set. `PUBLIC_ORIGIN` and `EXTRA_ORIGINS` were changed, deliberately
  and as recorded above.
