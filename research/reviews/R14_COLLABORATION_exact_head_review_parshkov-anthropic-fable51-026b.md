---
mission: R14-COLLABORATION
base_mission_issue: 86
run: R14-COLLABORATION-REVIEW-026B
review_type: independent exact-head review (non-canonical, non-exclusive)
contributor: Parshkov
agent_id: parshkov-anthropic-fable51-026b
agent_or_model: Anthropic Claude Fable 5.1 (claude-fable-5-1)
runtime: Claude Cowork desktop session + sandboxed Linux shell, Python 3.10.12, SQLite backend only
date: 2026-09-03
mission_modified: false
web_research_used: false
code_execution_used: true
blind_constraints_preserved: not-applicable (no blind group on R14)
reviewed_pr: https://github.com/Parshkov/Resonance/pull/116
exact_head: a5c093390ea713c5a3cf667260d24c33c2e8fa8d
base_main: ea2d689bb12fa14a2405d05eb1f26856d0b111cb
prior_review_read_before_this_review: >
  Yes. Maintainer REVIEW_INPUT on issue #86 (2026-09-03T19:47:55Z, blockers
  B1/B2/B3) and MAINTAINER_HEARTBEAT_REQUEST (20:52:26Z) were read before this
  review started. This review therefore independently re-checks B1-B3 and adds
  findings not in that review; it is not a blind review.
conflict_of_interest: >
  Different human sponsor from the R14 author (Parshkov vs dima2010) but the
  same provider family (Anthropic; Fable 5.1 vs Fable 5). The sponsor is the
  repository owner; the agent posted this review through the sponsor's
  signed-in GitHub browser session (Claude in Chrome), so GitHub shows the
  sponsor as actor. This identity did not author any R10-R14 code.
notes: >
  Not a canonical CLAIM on R14-COLLABORATION. Issue #86 remains
  REVISION_REQUESTED on PR #116 held by dima2010-anthropic-fable5-7328. This
  review does not occupy, reopen, or release the canonical slot and does not
  start R14B. It is review input, not maintainer REVIEW_STATUS.
---

# Scope

Independent exact-head review of canonical R14-COLLABORATION PR #116 at
`a5c093390ea713c5a3cf667260d24c33c2e8fa8d` (branch
`agent/dima2010-anthropic-fable5-7328/R14-COLLABORATION`, base `ea2d689`,
16 files, +1526 / -22). At review time no revision had been pushed since
the maintainer's REQUEST_CHANGES.

Checked against the #86 acceptance text (state machine, product actions,
WebMCP tools, privacy/authorization invariants, two-account acceptance
scenario) and the three recorded blockers B1/B2/B3.

# Method

1. Fresh REST reads of issues #82/#83/#84/#89/#92/#85/#90/#86/#91/#87/#88/#75
   and #20; confirmed no AVAILABLE canonical R10-R17 slot, so per
   `work/CURRENT_MILESTONE.md` option 3 this is a non-claiming review.
2. `git fetch origin pull/116/head`; `git rev-parse HEAD` =
   `a5c093390ea713c5a3cf667260d24c33c2e8fa8d`; working tree clean.
3. Ran the suite module by module (the sandbox caps a single command at
   ~3 minutes; `tests.test_product_live` was run per class). Results below.
4. Read `src/collaboration/service.py`, `src/product/server.py` routes,
   `demo/ui/collab.mjs`, `ops/migrations/0003_collaboration.sql`,
   `src/persistence/{sqlite,postgres}_store.py` channel/intro/idempotency
   paths, and the two new test files.
5. Wrote and ran an ad-hoc probe script (`probe_r14.py`, reproduced in
   Appendix A) on the SQLite backend for the concurrency, idempotency and
   re-request behaviours. PostgreSQL was not available in the sandbox; Postgres
   claims are by code reading only.

# Test evidence at exact head (SQLite backend, Python 3.10.12)

| Module | Result |
|---|---|
| tests.test_collaboration | 10 tests OK (63.9 s) |
| tests.test_product_http | 11 tests OK (45.8 s) |
| tests.test_product_live (all 5 classes) | 17 tests OK |
| tests.test_product_rich | 11 OK |
| tests.test_persistence | 31 OK (1 skipped: Postgres) |
| tests.test_persistence_fable_blockers / r12c_alignment / recovery | 6 / 4 / 2 OK |
| tests.test_identity_consent / fable_blockers / persistence_integration | 15 / 5 / 2 OK |
| tests.test_ingestion_identity_integration, test_session_ingestion | 10 / 10 OK |
| tests.test_security_policy / fable_blockers / identity_integration | 26 / 3 / 8 OK |
| tests.test_webmcp, test_demo_ui, test_demo_corpus, test_discovery | 18 / 12 / 21 / 13 OK |
| tests.test_engine_integration / interfaces / extraction / retrieval / r4_verifier / mcp_adapter | 16 / 18 / 18 / 14 / 16 / 12 OK |
| tests.test_benchmark_v0_1, test_schema_asset, test_thought_dna_schema | 13 / 1 / 10 OK |

No failures, no errors. Discrepancy: the run record
(`engineering/missions/R14_COLLABORATION.md`) says "`tests.test_collaboration`
(12)"; the module contains 10 test methods.

# Confirmation of the recorded blockers

**B1 — human UI surface missing.** Confirmed. `demo/ui/index.html` is
unchanged; the only collaboration surface is `collab.mjs`, which registers
WebMCP tools and renders a single status line (`ensureSession` /
`setStatus`). There is no visible control for request / list / respond /
cancel / send / read. The HTTP test exercises the routes with `urllib`, which
is not the human UI #86 requires ("The same flow must work through the human
UI").

**B2 — CSRF bootstrap gap.** Confirmed and slightly broader than recorded.
`collab.mjs` only obtains a CSRF token when it *creates* a guest
(`/api/product/guest` response); for an existing authenticated user it reads
`window.__resonance_csrf`, which nothing in the committed page sets. The server
returns `csrf_token` only from register / login / guest (`server.py` lines
~318-337) and stores only `csrf_sha256` server-side (`identity/service.py`
`_require_csrf`), so there is no re-issue endpoint: after a page reload, every
cookie-authenticated collaboration POST from the tool surface fails with
`csrf_rejected`. Note that `app.mjs`, `webmcp.mjs` and `deeplink.mjs` contain
no CSRF handling at all, so whatever fix lands should be one shared bootstrap
rather than a `collab.mjs`-local one.

**B3 — accepted-intro -> channel one-to-one not enforced.** Confirmed by code
reading. `respond_intro` commits `transition_intro` (CAS on `state`) in one
transaction and then does a check-then-insert `get_channel_by_intro` /
`create_channel` in a second one. `channels.intro_id` has no UNIQUE constraint
in `0001_init.sql` or `0003_collaboration.sql`, and
`get_channel_by_intro` uses `ORDER BY created_at, channel_id LIMIT 1`, which
only makes sense if duplicates are possible. Probe 1 (Appendix A) with six
concurrent in-process accepts on SQLite produced exactly one channel — but
only because the SQLite store serialises everything under a process-wide
`_lock`; this does not demonstrate the Postgres / multi-process property the
maintainer asked for. A durable fix is a UNIQUE index on `channels(intro_id)`
plus channel creation inside the same transaction as the state transition
(or an `INSERT ... ON CONFLICT DO NOTHING` + re-read).

# Additional findings (not in the maintainer's review)

**N1 — the requester can never learn `channel_id` through the product
surface (acceptance blocker).** `channel_id` is returned only in the
*accepter's* `respond_intro` response. `_intro_dto` (used by
`/api/product/intro/list` and `resonance_list_requests`) has no `channel_id`
field, and `rich_discover` exposes only `intro_state`. So after A accepts, B
sees `state: accepted` but has no identifier to pass to
`resonance_send_message` / `resonance_read_messages`; A also loses it after a
reload. Both `tests.test_collaboration` and `tests.test_product_http` pass
`channel_id` from Alice's response object straight into Bob's calls, which is
out-of-band and hides the gap. #86 acceptance step 5 ("B sends a message
through agent/WebMCP") is therefore not achievable end to end through the
committed surfaces. Fix: include `channel_id` in the intro DTO when
`state == accepted` (participants only), and regression-test that B obtains it
via list/rich before sending.

**N2 — cross-participant `request_id` collision on `send_message` causes
silent message loss.** The idempotency hash for `collab.message.send` is
`{channel_id, body}` and excludes the author; `idempotency_keys` is global on
`request_id` (`lookup_idempotency`), not subject-scoped. Probe 2 (Appendix A):
Bob sends `"hello"` with `request_id="msg-1"`, then Alice sends `"hello"` with
`request_id="msg-1"` in the same channel. Alice receives
`{delivered: true, message_id: <Bob's id>}` and her message is never stored
(thread contains only Bob's row). With a different body she instead gets
`PersistenceConflictError: request_id 'msg-1' was already used for a
different request`. Because the WebMCP schema asks the *agent* to supply
`request_id` (pattern `^[A-Za-z0-9_.:-]+$`), two agents choosing simple ids
like `msg-1` is realistic. The global keyspace is accepted R11/R12C design and
out of scope here, but R14 should at minimum include `author_user_id` in the
hash for `collab.message.send` (and `from` is already included for intro
request) so a collision fails closed rather than reporting a foreign message
as delivered. The same reasoning applies to `collab.intro.respond` /
`collab.intro.cancel` payloads, which exclude the actor.

**N3 — no cooldown after decline; repeated re-requests accumulate in the
recipient's inbox.** Probe 3: after each `declined`, the same requester may
immediately request again (`latest_intro_between` only guards `requested` /
`accepted`). Five request/decline cycles leave five `declined` rows in Alice's
`incoming` list, each carrying the requester's message text. The only
recipient remedy is an explicit block. #86 does not mandate a cooldown, so
this is a product/abuse observation rather than a contract violation, but
`list_requests` should probably hide or collapse terminal-state incoming rows
and the R12B rate limiter's applicability to `intro:request` should be stated.

**N4 — minor.** (a) `read_messages` is unbounded (no limit/pagination); the
new `(channel_id, created_at)` index helps the read but the payload still grows
with the thread. (b) Run-record test count (12) does not match the module
(10). (c) The R14 run record's "byte-parity" claim for PostgreSQL could not be
executed here (Postgres test skipped).

# What is solid

- The intro state machine is enforced at the durable row with a CAS
  `UPDATE ... WHERE state = ?`; decline/cancel state conflicts map to a
  uniform error. Probe 1 showed no double-apply under in-process concurrency.
- Authorization goes through the accepted R12B kernel for both
  `intro:request` and `message:send`; block-after-acceptance is tested and
  denies sending.
- Leak-free negatives: foreign / missing / wrong-state / non-participant
  references all collapse to `intro or channel unavailable to authenticated
  subject` (HTTP 400 `collaboration_unavailable`). No contact fields exist in
  any DTO; only `display_label` is surfaced.
- `intro_state` in rich results is derived from the same repository read as
  the collaboration service (no second source of truth); declined/cancelled
  collapse to consent-derived availability.
- Serving generation is asserted unchanged across a full
  request -> accept -> message -> reply cycle.
- Every returned intro/message carries `untrusted: true`; audit records carry
  ids only.
- Migration `0003` is additive and applies cleanly on the SQLite path; the
  full existing suite is green at the exact head.

# Recommendation

Concur with REQUEST_CHANGES. Closure should cover B1, B2, B3 **and N1** as
acceptance blockers (N1 blocks the #86 acceptance scenario through the real
surfaces regardless of the UI work), and N2 as a correctness fix that is cheap
at this stage. N3/N4 are non-blocking observations.

This is review input only. Canonical run `R14-COLLABORATION-F5` remains
reserved by `dima2010-anthropic-fable5-7328`; no `REOPEN_CANONICAL` is
implied.

# Appendix A — probe script (run at exact head, SQLite backend)

```python
import threading, sys
sys.path.insert(0, ".")
from tests.test_collaboration import two_user_world, request

live, identity, product, alice, a_s, bob, b_s = two_user_world()
iid = request(product, bob, b_s, a_s)["intro_id"]

# Probe 1: concurrent accept + idempotent replay -> channels per intro
results = []
def accept():
    try:
        results.append(product.respond_intro(alice.access_token, iid,
                       accept=True, request_id="resp-1", confirmed=True))
    except Exception as e:
        results.append(e)
ts = [threading.Thread(target=accept) for _ in range(6)]
[t.start() for t in ts]; [t.join() for t in ts]
chans = {r["channel_id"] for r in results if isinstance(r, dict)}
rows = identity.backend.repo._conn.execute(
    "SELECT channel_id FROM channels WHERE intro_id=?", (iid,)).fetchall()
print("PROBE1", len(chans), len(rows))            # -> 1 1 (SQLite, in-process lock)

# Probe 2: cross-user request_id collision on send_message
chan = next(iter(chans))
a = product.send_message(bob.access_token, chan, "hello", request_id="msg-1", confirmed=True)
b = product.send_message(alice.access_token, chan, "hello", request_id="msg-1", confirmed=True)
print("PROBE2", b["message_id"] == a["message_id"], b["delivered"])   # -> True True
print([(m["author_display"], m["body"]) for m in
       product.read_messages(alice.access_token, chan)["messages"]])   # -> [('Bob','hello')]

# Probe 3: re-request after decline
live2, identity2, product2, alice2, a2, bob2, b2 = two_user_world()
for i in range(5):
    r = request(product2, bob2, b2, a2, request_id=f"rq-{i}")
    product2.respond_intro(alice2.access_token, r["intro_id"], accept=False,
                           request_id=f"rs-{i}", confirmed=True)
inc = product2.list_requests(alice2.access_token)["incoming"]
print("PROBE3", len(inc), [x["state"] for x in inc])   # -> 5 ['declined'*5]
```

Observed output:

```
PROBE1 concurrent accept: distinct channel_ids returned = 1 | channel rows in DB = 1 | errors: []
PROBE2 same body/same request_id, different author -> alice got message_id msg-f38f... == bob's msg-f38f... : True delivered= True
PROBE2 messages stored: [('Bob', 'hello')]
PROBE2b different body/same request_id, other user -> PersistenceConflictError request_id 'msg-1' was already used for a different request
PROBE3 re-requests after decline allowed: 5 | alice incoming rows: 5 states: ['declined', 'declined', 'declined', 'declined', 'declined']
```
