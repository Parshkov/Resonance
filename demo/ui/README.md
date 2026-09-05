# R9 visual client

This is the competition-recordable Resonance discovery surface. It is an
offline-first presentation client over the accepted
`resonance-discovery/0.1` response. The browser does not match, retrieve,
rerank, verify, threshold, or calculate scores.

## Launch

From the repository root, with Python 3.10 or newer:

```bash
# Deterministic capture from the genuine accepted R8 fixture
python3 -m demo.ui.serve --source replay

# Accepted R8 discover_resonance MCP call, then the same renderer
python3 -m demo.ui.serve --source live
```

Open <http://127.0.0.1:8765/>. Both modes remain switchable in the header.
The request is pinned in both paths to:

```text
mode=analogical
k=15
```

REPLAY returns
`src/discovery/fixtures/example_response.json` byte-for-byte. LIVE starts the
accepted `src.discovery.demo_server`, performs MCP `initialize`, calls
`discover_resonance`, and renders its accepted DTO through the same frontend.
Verify the two paths without opening a browser:

```bash
python3 -m demo.ui.serve --verify-sources
```

The expected flagship session order is:

1. `ses-gabe-warehouse`
2. `ses-kwame-traffic`
3. `ses-mei-battery-heat`
4. `ses-noah-org-overload`

The frontend selects the first four discoverable, non-hard-rejected
`analogical` rows by iteration. It never sorts them. All other returned rows
remain accessible in the secondary drawer, while hard rejections appear only
as contradictions.

## The page

The page is a normal scrolling document with no fixed-height panels, so
nothing is clipped out of reach at any viewport (390×844 through
1920×1080). A visitor who has shared nothing sees the onboarding page
(`#app-shell[data-state="unshared"]`); a rendered result shows, in reading
order:

1. **Your thought** — the Thought DNA nodes and typed relations that are
   discoverable, with the domain and coarse location that were consented to.
2. **Resonance map** — a map of *structural relationship*, not geography.
   Every position is a function of numbers in the discovery response and
   nothing else:
   - distance from the centre = `1 − scores.structural` (inner ring 1.0, rim 0);
   - sector = `display.cluster_id`, lettered in the key under the map, in
     order of first appearance;
   - angle inside a sector = backend order;
   - line weight = `evidence.preserved_relation_count`;
   - dashed = `evidence.contradiction_count > 0` or a hard rejection.
   The number on every marker is the row's position in the engine's returned
   list (`01`… for `matches[]`, `R1`… for `rejected[]`), so the backend order
   is recoverable from the map, the cards and the drawer alike. Coarse
   location is an annotation on a match and never affects position or ranking.
3. **Resonances** — the first four eligible rows in backend order, never
   sorted; every other returned row stays inspectable in the drawer.
4. **Evidence** — the node-to-node correspondences and preserved relations the
   engine returned for the selected match. The query side of a preserved
   relation is resolved from the visitor's own Thought DNA; the candidate side
   is shown as the id the engine returned, because the other person's
   relations are not in the response.

The footer states the source (`REPLAY` is the accepted fixture with example
personas; `LIVE` is the visitor's own discovery), the corpus snapshot and the
discovery contract.

## Browser WebMCP (R10)

R10 adds a progressive browser transport using the WebMCP imperative API. It
is deliberately separate from the classic stdio MCP used by the LIVE R9 source.
The browser page registers tools through `document.modelContext.registerTool`;
those tools call the same accepted discovery data path rather than implementing
matching in JavaScript.

Launch the WebMCP-capable page:

```bash
python3 -m demo.ui.webmcp_server --source replay
# or use --source live for the accepted live discovery path
```

Open `http://127.0.0.1:8765/` in a WebMCP-capable browser. Localhost is suitable
for local verification as a potentially trustworthy origin; a hosted judge run
must use HTTPS. A visible `WebMCP · 6 tools` badge appears only after all six
`registerTool(...)` promises resolve successfully.

Registered browser tools:

- `resonance_prepare_thought` — creates only a private draft; it does not index or share.
- `resonance_get_share_preview` — read-only preview of exactly what would be shared; returns the opaque confirmation token required by the share call.
- `resonance_share_prepared_thought` — requires explicit confirmation plus the preview token.
- `resonance_discover` — read-only accepted structural discovery, backend order preserved; returns an opaque `result_id` for this exact response.
- `resonance_get_match` — read-only evidence projection requiring both the `result_id` returned by discovery and a `session_id`; it cannot silently switch source/result.
- `resonance_update_consent` — revokes discoverability immediately. It cannot bypass the safe share flow to re-enable a private thought.

### Discovery-result fidelity

A WebMCP discovery response is retained as a bounded in-process result record
and receives a deterministic opaque id such as `result-...`. The record binds:

- the requested source (`live` or `replay`);
- the exact accepted discovery payload returned by that call;
- every later evidence lookup performed with that `result_id`.

`resonance_get_match` does **not** reload the replay fixture and does not accept a
free-standing `source` argument. It resolves the requested session only inside
the exact discovery payload identified by `result_id` and returns the bound
source alongside the evidence. At most eight recent result records are retained
in R10 demo state. Sharing a newly prepared thought or revoking discovery
consent clears the retained result records, so an old result id cannot be reused
across a consent/thought-state transition.

This is specifically what keeps `LIVE discover -> get_match` on LIVE evidence
instead of silently falling back to REPLAY.

### Retry-safe write contract

Every state-changing tool input includes a required `request_id`. The caller
must create one stable idempotency key for the **logical operation** and reuse
that exact value if a timeout/cancellation causes a retry.

Accepted format: 1–128 characters from `A-Z a-z 0-9 _ . : -`.

The R10 adapter stores the committed result under `(operation, request_id)`:

- an exact retry returns the already committed result and does not apply the mutation twice;
- reusing the same key with different input fails with `idempotency_conflict`;
- committed-operation status is readable at
  `/api/webmcp/operation?operation=<prepare|share|consent>&request_id=<id>`;
- an unknown operation key returns `operation_not_committed` with
  `retryable=true`;
- validation/auth/confirmation/idempotency failures are explicitly
  `retryable=false`;
- after every successful or reconciled write, the browser re-reads
  `/api/webmcp/state` and renders that authoritative state instead of assuming
  its optimistic mutation succeeded.

If the WebMCP execution signal aborts while a write may already have reached the
server, the browser checks the operation ledger briefly. If the write committed,
it returns that stored result and refreshes authoritative state; if no commit is
found, the original `AbortError` remains an abort. This means cancellation never
pretends a committed write disappeared.

This in-process ledger is intentionally the R10 demo boundary. R11 must make the
same idempotency contract durable when the transport is wired to persisted
multi-user product state.

### Suggested judge sequence

Use a fresh stable request id for each logical write; the examples below use
human-readable placeholders.

1. Discover the WebMCP tools in the browser.
2. Call `resonance_update_consent` with `request_id="judge-revoke-1"` and `shared=false` so the demonstration starts private.
3. Confirm `resonance_discover` fails closed while private.
4. Call `resonance_prepare_thought` with `request_id="judge-prepare-1"`; this produces a private draft only.
5. Call `resonance_get_share_preview`, inspect the structured fields, and retain its `confirmation_token`.
6. Call `resonance_share_prepared_thought` with `request_id="judge-share-1"`, `confirm=true`, and that exact `confirmation_token`.
7. Repeat step 6 with the **same** `request_id` and arguments; the returned result must be identical and no second write is applied.
8. Call `resonance_discover` with `source="replay"` for deterministic verification or `source="live"` for the accepted live path. Retain the returned `result_id`.
9. Call `resonance_get_match` with that exact `result_id` and one returned `session_id`. Confirm the response reports the same source and the visible evidence card opens when that match is present in the flagship UI.
10. For the source-fidelity check, repeat steps 8–9 with `source="live"`; the match response must still report `source="live"` and evidence must originate from that exact LIVE result.
11. Revoke again with a new idempotency key; a subsequent discovery call must fail closed and prior `result_id` values must no longer resolve. A direct `shared=true` consent call is rejected; restoration again requires prepare -> preview -> explicit share.
12. Cancellation/reconcile check: issue a write with a stable key, cancel/lose the client response after dispatch, then retry that same logical operation/key. The stored committed result must be returned if the server committed it, and the human UI must reflect `/api/webmcp/state`.

WebMCP write endpoints are same-origin, bounded JSON requests. Browser writes
with a foreign `Origin` or `Sec-Fetch-Site: cross-site` are rejected; originless
writes are accepted only from a loopback peer for local command-line testing.
The page adds `Permissions-Policy: tools=(self)`, a same-origin CSP/COOP policy,
static schemas/descriptions, read-only annotations on reads,
`untrustedContentHint` on user-generated result surfaces, and forwards the
WebMCP execution `AbortSignal` to browser fetches. Registrations are owned by an
`AbortController` as required by the current imperative API.

The share preview itself is read-only: it does not flip server state. Instead it
returns an HMAC-based opaque confirmation token. The share endpoint requires
that token and clears the prepared draft after a successful share; prepare and
revocation rotate the token secret so stale previews cannot re-share later.

This R10 demo state is intentionally in-process and single-user. Durable
multi-user persistence, authentication/identity, retention, and the broader
security gate are owned by R11/R12/R12B rather than being faked here.

## Privacy and boundaries

- Only rows with `display.share_state=discoverable` can render.
- Missing location stays missing; Gabe is shown as `Location not shared`.
- Locations are coarse/synthetic annotations on a match and never affect
  ordering or map position.
- Hard rejections are segregated into the rust contradiction treatment.
- No contact details are requested or rendered.
- The page states that an introduction needs both sides; the R9 page itself
  requests none (`request_intro` is not an accepted R8 MCP tool), the live
  Collaboration drawer does.
- The UI imports no engine, alignment, retrieval, verifier, fingerprint, index,
  or scoring internals.

The server uses only the Python standard library. The browser uses native HTML,
CSS, JavaScript modules, and deterministic inline SVG. There is no build step,
package-manager dependency, web font, map tile, analytics call, or remote
runtime asset.

## Validation

```bash
python3 -m unittest tests.test_demo_ui -v
python3 -m unittest tests.test_webmcp -v
python3 -m unittest discover -s tests
node --check demo/ui/app.mjs
node --check demo/ui/webmcp.mjs
git diff --check
```

`tests.test_webmcp` includes duplicate-write idempotency, idempotency-key
collision, response-loss/cancel reconciliation, authoritative-state refresh
source assertions, confirmation-token safety, revocation, privacy projection,
cross-origin write checks, and a LIVE-source sentinel regression proving that
`get_match` reads the exact discovery result rather than replay fallback.

Native browser acceptance additionally requires a WebMCP-capable secure-context
browser to discover the six tools with `getTools()` / browser-agent discovery
and invoke at least the read and write/share/retry flows above. Source tests are
not a substitute for that browser evidence.

Design and implementation provenance is recorded in
[`PROVENANCE.md`](PROVENANCE.md),
[`WEBMCP_PROVENANCE.md`](WEBMCP_PROVENANCE.md), and
[`../../.superdesign/design-system.md`](../../.superdesign/design-system.md).
