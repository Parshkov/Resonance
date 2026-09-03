# R14-COLLABORATION — run record

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

```
python3 -m unittest tests.test_collaboration -v
python3 -m unittest tests.test_product_http
python3 -m unittest discover -s tests
```
