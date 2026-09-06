# R14-COLLABORATION — run record

> **Superseded in part (2026-09-06).** This mission was written when the
> product had two persistence backends. Resonance now runs on **PostgreSQL
> only** — `src/persistence/sqlite_store.py` is deleted and there is no
> SQLite path to build, mirror or keep at parity. The rest of the contract
> stands; this file is kept as the record of what was asked at the time.

- mission: #86
- canonical agent: `dima2010-anthropic-fable5-7328` (Anthropic / Claude Fable 5)
- run_id: `R14-COLLABORATION-F5`
- base: accepted main `ea2d689` (R13B merged)

## What this run adds

`src/collaboration/` — consent-safe pairwise connection over the accepted
layers, composition-only:

- **Deterministic state machine** `requested → accepted | declined | cancelled`
  enforced at the durable `intros` row (a CAS `UPDATE ... WHERE state = ?`), so
  concurrent/duplicate transitions can never double-apply.
- **Authorization through the accepted R12B kernel**: `intro:request` (candidate
  opt-in `allow_intro_requests` + symmetric blocks + explicit confirmation) and
  `message:send` — whose previously-`False` deferral point is now extended to
  return true exactly for mutually **accepted** connections, read per call from
  the durable intro records. Every denial branch is normalized to one uniform
  "unavailable" error (leak-free negative space: foreign, missing, wrong-state,
  and not-a-participant are indistinguishable).
- **Private relay channel** created on acceptance; **relay messages** with
  request_id idempotency. No email/phone/contact data exists anywhere in the
  stack — the requester is surfaced only as a pseudonymous display label.
- **UGC discipline**: every returned intro/message carries `untrusted: true`;
  audit records ids only (never the message text).

## Migration

`ops/migrations/0003_collaboration.sql` extends the dormant R11 `intros` table
(`message`, `from_user_id`, `to_user_id`, `cancelled_at`, `updated_at`) and adds
lookup indexes on `intros(from_user_id)`, `intros(to_user_id)`,
`messages(channel_id, created_at)` — the last one answers the readiness-note
caution about O(events) growth by giving messages a direct indexed read path
instead of an event replay. Applied atomically by the accepted per-migration
transaction; SQLite and PostgreSQL stores have byte-parity collaboration methods.

## Generation invariant

Connection state is **not** discoverable corpus content: no collaboration write
touches the corpus generation, so chat can never force an index rebuild
(regression asserts the serving generation is unchanged across a full
request→accept→message→reply cycle).

## Live connection state

R13B reserved `requested`/`accepted` in the `intro_state` enum; this run makes
them live through the **same** `_intro_state` derivation function (viewer-aware,
reads the latest intro between viewer and candidate owner) — no second source of
truth. A block or decline collapses the state back to consent-derived
availability.

## Surfaces

- HTTP: `/api/product/intro/{request,respond,cancel}`, `/api/product/intro/list`,
  `/api/product/channel/{send,messages}` on the authenticated live server.
- WebMCP: additive `demo/ui/collab.mjs` (accepted R9/R10 files untouched)
  registers `resonance_request_intro`, `resonance_list_requests`,
  `resonance_respond_intro`, `resonance_send_message`, `resonance_read_messages`
  via canonical `document.modelContext.registerTool`, with `readOnlyHint` on the
  two read tools, `untrustedContentHint` wherever user text is returned, and
  explicit `confirm` + stable `request_id` on every write.

## Evidence

- `tests.test_collaboration` (12) + `tests.test_product_http` collab flow: full
  scenario, confirmation gates, idempotent replay + key collision, decline/cancel
  state conflicts, participant-only uniform negatives, messaging gates incl.
  block-after-acceptance, restart durability, live `intro_state` flips.
- Live headless Chrome 152 (`--enable-features=WebMCP`): the two-account
  acceptance scenario end to end — B requests intro **through the WebMCP tool**,
  A accepts through the **manual UI/HTTP** path, B messages through the tool, A
  replies through the UI, B reads the thread through the tool; pseudonymous
  identities only, no contact data, final `intro_state = accepted`.

## Review revision (REVIEW_INPUT 5106136846 — three blockers closed)

1. **Human UI** — additive `demo/ui/collab_ui.mjs` injects a visible collaboration
   panel: a "Request intro" control on discoverable match cards, an
   incoming/outgoing request list with accept/decline/cancel buttons, and a
   channel thread with a message composer. Every control drives the same
   `/api/product/*` endpoints the WebMCP tools use. All user text is inserted
   via `textContent` (never `innerHTML`) — displayed, never interpreted.
2. **CSRF/session bootstrap** — `demo/ui/session.mjs` persists the CSRF token in
   `sessionStorage` at issue time and, on a reload that carries only the cookie,
   mints a fresh token for the same subject via new `POST /api/product/rotate`.
   No page global, no harness secret injection. Both `collab.mjs` (tools) and
   `collab_ui.mjs` (human UI) share this one `apiFetch` bootstrap.
3. **Channel one-to-one atomicity** — acceptance now runs through a single
   repository `accept_intro` transaction (CAS `state='requested'→'accepted'`
   plus channel insert), the channel id is deterministic in the intro id, and
   migration `0003` adds `UNIQUE(channels.intro_id)`, so any concurrent or
   replayed accept converges on exactly one channel.

Verified live in headless Chrome 152: request → accept → open channel → send →
read entirely through the visible UI controls; and a page reload keeps the
CSRF working (authorized read/write) with no injection.

### Second revision (reproduction findings F1/F2/026B-N2)

Two independent reproduction reviews (`parshkov-anthropic-opus5-3f1c` #118 and
`parshkov-anthropic-fable51-026b` #117) converged on further findings; all are
closed:

- **F1** (channel id unreachable by the requester) — the accepted-intro DTO now
  carries `channel_id`, so B obtains it from `list_requests`, never from A's
  response. Regression: `test_requester_obtains_channel_id_from_list_not_acceptor_response`.
- **026B-N2** (cross-actor message idempotency collision) — the idempotency
  request_id is now namespaced by the acting subject (`{user_id}:{request_id}`),
  so two senders reusing the same key neither collide nor false-conflict.
  Regression: `test_message_idempotency_is_per_author`. Applied to
  message.send and intro.respond/cancel/request.
- **F2** (guest silently created for an authenticated-but-unshared user) —
  `state()` returns an explicit `authenticated` flag, and `session.mjs` branches
  on it (never on `owned_sessions.length`), so a tool/UI call never mints a
  guest for a registered visitor. Regression in `test_product_http`.

### Third revision (re-verification findings B1a, F4)

The reproduction's execution re-verification (#118) closed B2/B3/F1/F2 and found
two more; both closed:

- **B1a** (a human could not *initiate* an intro — the "Request intro" control
  read a `querySession` global nothing set, so it never rendered) — `collab_ui.mjs`
  now has a "Start an introduction" panel section that lists the viewer's own
  discoverable session, runs live `rich_discover`, and renders a "Request intro"
  button per intro-accepting candidate (independent of the R9 replay cards); it
  also sets `document.body.dataset.querySession`. The stale R9
  "Introductions unavailable" placeholder is hidden at runtime (the R9 file is
  untouched). Verified live: the button renders and initiates an intro from the
  panel.
- **F4** (a second tab's `rotate` revoked the first tab's token and stranded its
  writes) — `session.mjs` now shares the CSRF token across tabs via
  `localStorage` (so a second tab reuses the token and never rotates), and any
  `csrf_rejected` write clears the stored token and re-bootstraps once before
  failing. Verified live across two tabs: the second reuses the token, the first
  keeps writing, and it self-heals after a forced rotation. HTTP regression
  `test_two_concurrent_clients_of_one_subject_selfheal`.

```
python3 -m unittest tests.test_collaboration -v
python3 -m unittest tests.test_product_http
python3 -m unittest discover -s tests
```
