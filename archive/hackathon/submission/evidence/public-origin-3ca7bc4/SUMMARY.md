# Onboarding landing page, live — `resonance.parshkov.com` @ `3ca7bc4`

- **Origin (canonical):** https://resonance.parshkov.com · **MCP:** …/mcp
- **Origin (platform host, still valid):** https://resonance-production-cfe3.up.railway.app
- **Commit:** `3ca7bc4` (#175 on top of `c3a55f8` = #174)
- **Railway:** project `670bcce5-…` / service `resonance` `172aa183-…` / env `production` `da338ecd-…`
- **Runner:** sponsor's macOS workstation, Python 3.12.8, Google Chrome 152.0.7977.83
- No tokens, codes or raw text in this directory.

## What changed on the live product

A first-time visitor no longer lands on an empty results dashboard. Removing the
fixture personas (#169) made the page honest; it did not make it usable. Opening
the origin now gives what Resonance is, what happens to a thought, and the
connector address — and the results dashboard appears only when there are
results.

Verified on the deployed origin in a real browser:

```
#app-shell[data-state]                 -> "unshared"
#onboarding-heading                    -> "Find the people whose reasoning matches yours."
.workspace > .surface (all three)      -> computed display: none
#mcp-url                               -> https://resonance.parshkov.com/mcp
fixture persona names anywhere on page -> none
"Bearer" / "Create MCP key" on page    -> none
documentElement.scrollWidth <= innerWidth -> true
```

The connector URL is derived from `window.location.origin`, so the page is
correct on either host; opened on the platform URL it shows that one instead.

Two adjacent untruths in the interface went with it:

- The Collaboration panel's "Connect your chat (MCP)" led with **Create MCP
  key** and handed out `Authorization: Bearer <key>` and a `…/mcp/<key>`
  capability URL — the path `ops/CONNECT_MCP.md` §2 calls "debug only" and
  `HUMAN_TEST_CARDS.md` calls a **FAIL**. The URL now leads; the key is behind a
  closed disclosure; the capability URL is not advertised at all.
- "Introductions unavailable — not exposed by the accepted R8 MCP", false since
  R13/R14, is replaced by the rule that is true: introductions need both sides.

## Acceptance on the canonical domain

| # | check | result | artefact |
|---|---|---|---|
| P1 | `GET /api/product/health` | ok, `resonance-engine/0.2`, `demo_personas_present: false` | `health.json` |
| P2 | `ops/hosted_onboarding_probe.py --smoke --refresh --revoke --json` | **9/9 required**, smoke share revoked | `hosted_onboarding_probe.{json,txt}` |
| P3 | `ops/oauth_smoke.py …/mcp --auto-consent` | **27/27** | `oauth_smoke.txt` |
| P4 | `submission/evidence/abc_mcp_test.py …/mcp` | **36/36**, all guests revoked, `still_discoverable=[]` | `abc.{json,txt}` |
| P5 | Card A — Chrome 152 + `--enable-features=WebMCP` | **24/24, `mode: NATIVE`** | `card-a-browser/` incl. 5 screenshots |
| P6 | R9 empty/error state | **18/18** | `r9_empty_state.{json,png}` |
| — | `python3 -m unittest discover -s tests` | **468 OK, 2 skipped** (348 s) | — |

The duplicate-removal result holds after the UI change: **`rank=0`** for the
genuine cross-domain analogy (`A (retry storm) found by B (panic buying) —
rank=0 score=1.0`), 4 matches returned rather than the pre-purge 12.

`card-a-browser/browser_01_native_load.png` is the deployed onboarding page as a
WebMCP browser sees it.

## A regression introduced and caught in this change

Leaving the onboarding state when consent changes needs no page reload, so the
page has to learn about it. Two attempts were wrong in the same way:

1. re-run discovery on every write;
2. ask a cheap consent endpoint on every write.

**Both broke Card A's revoke step with `authorization_failed: rate limit
exceeded`** — the limiter allows 30 tokens refilling at 1/s, and an extra read
per write is enough to starve an honest later tool call.

It was diagnosed rather than guessed: a `git worktree` of pristine `origin/main`
served on a second port, driven by the same browser and the same harness. Revoke
passed there and failed on the branch, so the regression was the branch's. The
accepted fix costs **zero** extra requests: `webmcp_live.mjs` and `collab_ui.mjs`
already hold the authoritative consent state after a write and now announce it
on a `resonance:consent` event; the page re-reads the live view only when the
answer flipped. After the fix both trees failed the *same* two local checks —
the two that need a non-empty corpus — and the deployed run above is 24/24.

Also measured, not assumed: `scrollIntoView({behavior: "smooth"})` does nothing
inside this nested scroll container in Chrome 152 (`scrollTop` stayed 0 where the
default moved it to 447), so the "Connect your chat" button was dead. Asking for
smoothness in CSS reproduces it, because the default then resolves to smooth.
It scrolls instantly and works.

## Deviations / not claimed

- Cards B, C, D and E remain **unexecuted** and are not claimed. Card A no longer
  needs a person: the harness reproduces it on any machine with Chrome 152+.
- Pre-existing and not fixed: `.footer-strip` wraps mid-token at 390px;
  `.app-shell { min-height: 720px }` with `body { overflow: hidden }` clips the
  shell below a 720px viewport height.
- The visual pass on `demo/ui/styles.css` was delegated to Fable 5.1 with the
  wording frozen; `index.html` was verified byte-identical afterwards and the
  onboarding text nodes unchanged.
- `RESONANCE_DB` and `RESONANCE_CONFIRMATION_SECRET` were neither read nor
  modified. `RESONANCE_SEED_DEMO` was never set. `RESONANCE_PURGE_SESSIONS` was
  set once for the duplicate removal (#174) and removed afterwards.
- Session counts keep growing across acceptance runs: every run revokes what it
  created, but a revoked row is not a deleted row.
