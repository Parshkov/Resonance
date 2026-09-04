# R15D — Hosted-client onboarding acceptance (ChatGPT / Claude)

**Lane #137.** Prove the final hosted-client user experience: a tester is handed
**only** the canonical resource URL and completes OAuth onboarding with no manual
secret. This document is the acceptance procedure + the <10-minute human test
cards. It owns acceptance tooling only — it does not modify the OAuth core
(#134), production routing (#136), or the browser WebMCP UI.

Canonical resource (the *only* thing a tester receives):

```
https://resonance-production-cfe3.up.railway.app/mcp
```

## Canonical UX under test

1. user adds the canonical MCP URL to the hosted client
2. client automatically discovers auth requirements (401 → resource metadata)
3. browser opens the Resonance authorization page
4. user signs in **or** continues as a pseudonymous guest
5. explicit OAuth consent for the requested scopes
6. browser returns to the hosted client with a single-use code
7. client exchanges the code and discovers Resonance tools
8. `resonance_whoami` succeeds in a fresh chat

**Forbidden in the normal acceptance path** (any of these = FAIL, report it):
creating/copying an MCP key; pasting a manual bearer token; a `/mcp/<secret>`
capability URL; a custom `Authorization` header supplied by the user.

## Automated pre-flight probe (run before any human step)

`ops/hosted_onboarding_probe.py` is a black-box, discovery-driven simulation of
exactly what a hosted client does. It is stdlib-only and imports nothing from the
server — point it at any origin. Run it against production the moment #136 reports
a green deployment; it fails fast with an exact per-step report if onboarding is
not actually connectable, so no human time is spent on a broken flow.

```bash
python3 ops/hosted_onboarding_probe.py --base https://resonance-production-cfe3.up.railway.app --smoke --refresh --revoke --json
```

Required steps (exit 0 iff all pass): unauthenticated `/mcp` 401 + resource
metadata → RFC 9728 protected-resource metadata → RFC 8414 authorization-server
metadata (S256) → consent page (GET) → approve → 302 code + exact `state` →
token (authorization_code + PKCE) → MCP `initialize` → `tools/list` →
`resonance_whoami`. Optional: post-connect smoke (prepare→preview→share→discover),
refresh rotation with old-token reuse rejected, revoke then reuse rejected.

A regression test (`tests/test_r15d_onboarding.py`) runs this probe against a
locally built server and **self-activates** once the R15A OAuth core is present
(it skips on a build that still ships only the demo OAuth).

## Human test card A — ChatGPT custom MCP app

*Requires a workspace with developer mode (ChatGPT Business / Enterprise / Edu).
This is the sponsor-only gate — it cannot be exercised from the build sandbox.*

1. ChatGPT → **Settings → Connectors / Apps → Advanced → Developer mode** (enable).
2. **Create** a custom app/connector. Endpoint / MCP server URL = the canonical
   `/mcp` URL above. Authentication = **OAuth** (let the client discover it).
3. Click **Scan / Connect Tools**. Expect a browser window to open on the
   **Resonance authorization page** (not an error, not a token prompt).
4. **Continue as guest** (or sign in with an existing Resonance recovery secret).
5. Approve the **consent** screen (scopes: `resonance.read`, `resonance.write`,
   `offline_access`).
6. The window returns to ChatGPT; tools are **discovered** (the `resonance_*`
   list). No key was ever copied.
7. In a **fresh chat**, invoke `resonance_whoami` → expect a `person-…` id.
8. Minimal smoke (optional, once whoami works): prepare the current/selected chat
   as a thought → preview → explicitly share → discover.

Record: exact production SHA, deployment id, screenshots/screen-recording of
steps 3–7, and the observed `person-…` id. Capture server logs **without
secrets**.

## Human test card B — Claude custom connector

*Where the account/plan supports adding a custom/remote MCP connector.*

1. Claude → **Settings → Connectors → Add custom connector** → URL = canonical
   `/mcp`.
2. Choose **OAuth** / let the client discover auth; complete the Resonance
   authorization + consent in the opened browser (guest or sign-in).
3. Connector shows **connected**; Resonance tools are listed.
4. In a new conversation, call `resonance_whoami` → `person-…`.

State honestly which client actually executed. **Never** claim compatibility for
a client that was not really connected.

## Failure-report schema

For every failure post, on the owning issue:

- client + product build + plan (if relevant)
- step number where it broke
- public URL
- visible error text
- HTTP status / redirect chain if observable
- did the auth page open?  did the callback return?  were tools discovered?
- blocker severity

If the blocker is in the OAuth core, report it on **#134** and WAIT; if in
production/routing, report on **#136**. Do not patch overlapping code from this
lane.

## Sponsor-only gate & truth-safe wording

The real ChatGPT (A) and Claude (B) executions need a sponsor account with the
custom-MCP/developer capability and cannot be run from the build sandbox. This
lane drives everything up to that gate — the automated probe proves the flow is
connectable, and the cards make the human step deterministic and short.

Wording for #75/#88 until a real hosted client has connected: *"Standards-based
OAuth onboarding (RFC 9728 / 8414 / PKCE S256) is implemented and verified
end-to-end by an automated hosted-client probe; live ChatGPT/Claude custom-app
connection is pending a sponsor developer-mode account."* Do **not** upgrade this
to a compatibility claim until card A or B has actually executed and the evidence
is captured.

## Status

- [x] Automated onboarding probe built and validated end-to-end (9/9 required +
      7/7 optional) against a conformant OAuth core.
- [x] Self-activating regression test committed (skips until R15A lands).
- [ ] Probe run against the production origin — **WAITING_ON #136** (green deploy
      of the reviewed #134 core).
- [ ] Human card A (ChatGPT) executed — **sponsor developer-mode account required**.
- [ ] Human card B (Claude) executed — where supported.
