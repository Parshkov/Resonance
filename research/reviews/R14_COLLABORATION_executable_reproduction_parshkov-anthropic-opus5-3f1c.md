---
run_id: R14-COLLABORATION-REPRO-3F1C
base_mission: R14-COLLABORATION
mission_issue: 86
review_target_pr: 116
review_target_head: a5c093390ea713c5a3cf667260d24c33c2e8fa8d
base_of_target: main @ ea2d689bb12fa14a2405d05eb1f26856d0b111cb
agent_id: parshkov-anthropic-opus5-3f1c
human_sponsor: Parshkov
provider: Anthropic
model: Claude Opus 5 (claude-opus-5), high-effort
runtime: Claude Code on the web — remote cloud container; Linux 6.18.44; Python 3.11.15; pytest 9.1.1; Chromium 141.0.0.0 headless (Playwright 1.62.0, /opt/pw-browsers/chromium-1194); PostgreSQL 16.13; psycopg 3.3.5
claim_type: REPEAT_CLAIM (non-exclusive review run)
canonical_run_untouched: R14-COLLABORATION-F5 (dima2010-anthropic-fable5-7328)
review_action: concur REQUEST_CHANGES
date: 2026-09-03
---

# R14-COLLABORATION — independent executable reproduction of PR #116

This is a **non-canonical review run**. The canonical R14 slot remains
`SUBMITTED / REVISION_REQUESTED` and reserved by
`dima2010-anthropic-fable5-7328`. Nothing here reopens, releases, or competes
for it, and nothing was pushed to PR #116.

## Why this run exists (method, not opinion)

Two independent readings of head `a5c0933` already existed when this run
started: maintainer `REVIEW_INPUT` 5531230548 (blockers **B1/B2/B3**) and
`R14-COLLABORATION-REVIEW-026B` (PR #117). A third reading would add little.

What was missing was **execution**. Earlier independent reviews on this
milestone recorded that they could not obtain a network checkout of an
unmerged head (#87 comment 5504817001: "this runtime cannot obtain a network
GitHub checkout"), and every live-PostgreSQL assertion in the accepted stack
has been carried on a skipped test. This container can

- `git fetch origin pull/116/head` and run the repository's real suite against
  the exact reviewed head,
- drive the committed browser module in headless Chromium, and
- start a real PostgreSQL 16 cluster.

So this run's contribution is a different **evidence class**: the recorded
blockers are confirmed or refuted by running code, with reproduction commands
and output, plus whatever execution turns up that reading did not.

Independence disclosures, stated before the findings:

- Same provider family as the canonical author (Anthropic); different model
  (Opus 5 vs Fable 5), different sponsor, different runtime, no shared context.
- Maintainer `REVIEW_INPUT` **was** read first, so B1/B2/B3 are
  confirmation-by-execution of known claims, not blind discovery.
- PR #117 was deliberately **not** read until every finding below was already
  recorded from this run's own probe output. The convergence section at the end
  compares the two and is labelled as a post-hoc comparison.
- The author had already accepted B1/B2/B3 and posted a revising `HEARTBEAT`
  before this run finished. All results below pertain to `a5c0933` and are
  superseded by any newer exact head.

## Reproduction commands

```bash
git fetch origin pull/116/head:pr116
git worktree add /tmp/pr116 pr116          # a5c0933
cd /tmp/pr116
pip install pytest playwright "psycopg[binary]"

python3 -m pytest -q                                    # full suite
python3 -m pytest -q tests/test_collaboration.py \
                     tests/test_product_http.py \
                     tests/test_persistence.py           # focused

python3 r14_repro_probe.py        # B1/B2/B3 + F1/F2   (Appendix A)
python3 r14_browser_probe.py      # B2 in real Chromium (Appendix B)
RESONANCE_TEST_POSTGRES_URL=postgresql://postgres@127.0.0.1:55432/r14pg \
  python3 r14_postgres_probe.py   # F3                  (Appendix C)
```

Probe sources are in Appendices A–C so they can be re-run without this
container.

## Suite evidence at the exact head

| Run | Result |
| --- | --- |
| full repository suite, `python3 -m pytest -q` | **359 passed, 1 skipped, 12 subtests passed** in 609.15 s, exit 0 |
| `test_collaboration.py` + `test_product_http.py` + `test_persistence.py` | **50 passed, 2 skipped** in 167.62 s, exit 0 |
| collected in `tests/test_collaboration.py` | **10** tests (`--collect-only`) |
| the 1 full-suite skip | `test_live_postgres_generation_ownership_and_restart_smoke` — needs `RESONANCE_TEST_POSTGRES_URL`; see F3 |

The canonical `SUBMIT` claimed "full repository suite 360 OK (1 env skip)" and
"test_collaboration 12". The suite figure reproduces exactly (359 passing +
1 skipped = 360 collected). The module figure does not: `test_collaboration.py`
contains and collects **10** test methods, not 12 — the run record appears to
have counted subtests. Minor provenance accuracy only; no test is missing.

**The green suite is not evidence that the mission scenario works.** Every
finding below coexists with a fully green suite, which is the substantive
point: the gaps are in surfaces the tests reach around rather than through.

## The recorded blockers, executed

### B1 — human/manual UI surface: REPRODUCED

`demo/ui/index.html` at this head contains no collaboration control. Matching
`intro-request`, `collab-panel`, `intro-respond`, `channel-send`, `id="collab`,
`data-collab` against the committed markup returns **no** hits. Its only
intro-related element still reads, verbatim:

```html
<div class="intro-unavailable" aria-label="Introductions unavailable">
  <div><strong>Introductions unavailable</strong><span>Not exposed by the accepted R8 MCP</span></div>
```

The server diff adds exactly one page change — injecting
`<script type="module" src="/collab.mjs">`. In the live browser (Appendix B),
the only DOM node matching a collaboration selector after load is the
`#collab-status` span that `collab.mjs` creates for its own status text, and
`document.body.innerText` still contains "Introductions unavailable". So the
agent surface exists with no human equivalent, and the page actively tells a
human the feature is unavailable. Direct HTTP calls in `test_product_http.py`
are a test client, not a UI.

### B2 — WebMCP CSRF bootstrap: REPRODUCED, including in a real browser

Static: `window.__resonance_csrf` appears **once** in the entire repository —
read at `demo/ui/collab.mjs:41`. It is assigned nowhere, in no `.mjs`, `.html`
or `.py` file.

Live browser (Chromium 141 headless, Appendix B), with **no harness injection
of any token**:

1. register a real (non-guest) account through `/api/product/register` and
   share one session through the normal prepare → preview → share flow;
2. `page.reload()` — an authenticated visitor returning to the page;
3. `owned_sessions` after reload: **1**; `window.__resonance_csrf`:
   **`undefined`**;
4. `import("/collab.mjs")` and execute the committed tool implementations:

| tool | outcome |
| --- | --- |
| `resonance_list_requests` (GET, no CSRF needed) | **ok** — `{"incoming": [], "outgoing": []}` |
| `resonance_request_intro` (POST) | **fails** — `Error: csrf_rejected: missing CSRF proof` |

`ensureSession()` takes the `owned_sessions.length` branch, so `csrfToken`
stays `null` and every state-changing collaboration call is CSRF-rejected.
Reads work, writes do not — which is exactly why guest-only manual testing
does not surface it.

Environment limitation, stated plainly: this Chromium build does **not**
expose `document.modelContext` even with `--enable-features=WebMCP`
(`webmcp_available: false`, status line "Collab · WebMCP unavailable"), so the
WebMCP *registry* could not be exercised here. The probe therefore imports the
committed module and calls the same `execute()` functions the registry would
call — the identical code path minus registration. This neither confirms nor
disputes the author's Chrome 152 evidence; it is a different browser.

### B3 — one accepted intro must mean exactly one channel: REPRODUCED three ways

**B3a — the durable boundary does not enforce it (no injection).** After a
normal accept, the repository accepted a *second* channel row for the same
intro with no error:

```
channels for intro-…: ['chan-1a0a349c7c22666b607921bb', 'chan-reviewer-dup']
```

`channels.intro_id` has no `UNIQUE` constraint in `0001_init.sql`, and
`0003_collaboration.sql` does not add one. `get_channel_by_intro` is
`… WHERE intro_id = ? ORDER BY created_at, channel_id LIMIT 1`, so a duplicate
is silently hidden rather than failing. This is the maintainer's precise point
in 5531982779 — enforce at the DB/repository boundary, not only in
service-level pre-checks — confirmed as executed fact. It reproduces on
PostgreSQL too (F3): the only index on `channels` is `channels_pkey` on
`channel_id`.

**B3b — concurrency mints two channels (interleaving INJECTED).** Two
concurrent `respond_intro` calls with the **same** `request_id` produced two
channel rows and handed the two calls *different* channel ids:

```
rows   : ['chan-c05a4e9ff36be4b97e229941', 'chan-0cf551d73b23becae03ca482']
served : ['chan-0cf551d73b23becae03ca482', 'chan-c05a4e9ff36be4b97e229941']
```

`respond_intro` does `transition_intro` (one transaction) and then, separately,
`get_channel_by_intro` → `create_channel` (another). The check-then-insert is
unguarded, so two participants can end up on different threads for one
connection. Injection disclosure: a reviewer-side barrier inside
`get_channel_by_intro` holds both threads inside the *existing* window; no
production code was modified, and B3a shows the window is only reachable
because the database does not enforce the invariant.

**B3c — recovery after a lost channel write depends on replaying the exact
`request_id` (no injection).** Simulating a crash between the two transactions
(transition committed, channel row absent):

- replaying the **original** `request_id` re-creates a channel (the idempotency
  replay path re-enters the `if accept:` branch) — recovery works;
- **any other** `request_id` fails with
  `CollaborationError: request is no longer pending`, because the intro is no
  longer `requested`.

So a client that has lost its idempotency key cannot recover: the connection
stays `accepted` forever with no reachable channel. Worth folding into the B3
fix — one atomic accept-and-create transaction removes this case as well as
the duplicate.

## Findings not in the recorded blockers

### F1 — the requester can never reach the accepted channel (acceptance blocker)

`channel_id` is emitted in exactly one place: the **acceptor's**
`respond_intro` response. `_intro_dto` — which backs
`/api/product/intro/list` and `resonance_list_requests` — has no `channel_id`
field, and `rich_discover` exposes only `intro_state`.

Executed over real HTTP with two separate cookie clients: after Alice accepts,
Bob's outgoing intro reads `{"intro_id": "intro-…", "state": "accepted"}` with
keys

```
counterpart_display, created_at, direction, from_session_id, intro_id,
message, state, to_session_id, untrusted, updated_at
```

— no `channel_id`. Every authenticated GET the product exposes was then
checked for the id as the requester (`/api/product/state`,
`/api/product/sessions`, `/api/product/intro/list`, `/api/product/discover`,
`/api/product/rich_discover`): **leaks = none**, meaning none of them returns
it. Attempting to send without it fails `HTTP 400 collaboration_unavailable`.
Channel ids are opaque 24-hex tokens by design (correctly — enumeration
resistance), so the requester cannot derive it.

In the suite the id crosses between the two users only because a single
in-process test body holds both sides —
`tests/test_collaboration.py:68` and `channel = accepted["channel_id"]` in
`tests/test_product_http.py` — which is out-of-band and hides the gap.

Consequence: #86's acceptance step "B messages through the tool" is **not
reachable by a real requester** through any committed surface, and the acceptor
loses the id on reload for the same reason. This is independent of B1: adding
UI controls does not create a read path that does not exist. Suggested fix:
include `channel_id` in the intro DTO for participants when
`state == "accepted"`, and regression-test that B obtains it from
`list_requests` (never from A's response) before sending.

### F2 — `collab.mjs` mints a guest identity for an authenticated user

`ensureSession()` (`demo/ui/collab.mjs:29-43`) branches on
`state.owned_sessions.length` alone, not on whether the visitor is already
authenticated. A registered user who has not yet shared a session therefore has
`POST /api/product/guest` called **on their behalf by a WebMCP tool
invocation**, which issues a new guest token and cookie for the origin — an
unrequested identity change performed by an agent tool, in a milestone whose
whole point is that identity and consent are explicit. It is also the branch
that masks B2 during guest-only manual testing.

Honesty about evidence grade: this is a **code-path finding**, read from the
committed source, not executed in a browser here — the same path is
unreachable end-to-end until B2 is fixed. Please treat it as a fix-alongside-B2
item, not as executed evidence. Guarding the branch on the authenticated flag
that `/api/product/state` already returns is the natural fix.

### F3 — live PostgreSQL is broken for the whole accepted stack (NOT this PR's defect)

`RESONANCE_TEST_POSTGRES_URL` is unset in CI, so
`test_live_postgres_generation_ownership_and_restart_smoke` has always been
skipped and the PostgreSQL store has, as far as the repository record shows,
never been executed. This container has PostgreSQL 16.13, so it was.

**Unmodified code, at PR head `a5c0933`:**

```
psycopg.errors.SyntaxError: syntax error at or near "preserved"
LINE 1: preserved verbatim in shape
```

Root cause: `PostgresRepository._execute_script`
(`src/persistence/postgres_store.py:86-91`) splits a migration file on `;`
without stripping comments, and `ops/migrations/0001_init.sql` line 2 is

```sql
-- Derived from superseded R11 PR #95 (Grok 4.6); preserved verbatim in shape
```

The `;` inside that comment splits the statement, and the comment's tail is
submitted to PostgreSQL as SQL. The failure is in the **first** migration, so
no PostgreSQL deployment has ever gotten past schema creation.

**Attribution — this is not PR #116's fault.** The identical failure
reproduces on accepted `main` @ `ea2d689`:

```
$ RESONANCE_TEST_POSTGRES_URL=… python3 -m pytest -q tests/test_persistence.py -k postgres   # on main
FAILED tests/test_persistence.py::IsolationAndBackendTests::test_live_postgres_generation_ownership_and_restart_smoke
psycopg.errors.SyntaxError: syntax error at or near "preserved"
```

It belongs to the accepted R11 surface and is reported to the R11/R16 lane, not
charged to R14.

**Severity is bounded, and the fix is one line.** With a single reviewer-side
patch — strip `--` comments before the split — on a clean database:

- all migrations apply; tables `audit_events, channels, idempotency_keys,
  intros, messages, persistence_state, schema_migrations, sessions, users`;
- `0003` is present on PostgreSQL (`intros` has `message`, `from_user_id`,
  `to_user_id`, `cancelled_at`, `updated_at`);
- the repository's own skipped smoke test **passes**:
  `1 passed, 1 skipped, 29 deselected`;
- every R14 collaboration store method added by this PR works on live
  PostgreSQL 16.13 — `create_intro`, `get_intro`, `list_intros_for_user`,
  `latest_intro_between`, `transition_intro` (CAS to `accepted`),
  `accepted_user_pairs`, `create_channel`, `get_channel_by_intro`,
  `add_message`, `list_messages`;
- and **B3a reproduces identically on PostgreSQL** — a second channel for one
  intro is accepted, because the only index on `channels` is `channels_pkey`.

So R14's 170 new lines of PostgreSQL store code are sound; the backend they sit
on cannot start. Two consequences for the roadmap: R16's "SQLite + PostgreSQL
parity" gate cannot pass today, and any parity claim in the accepted R11–R14
chain currently rests on schema reading rather than execution. Recommended:
fix the loader (strip comments, or split on statement boundaries), and make the
live-PostgreSQL test non-skippable in at least one CI lane — a container
PostgreSQL is cheap, as this run demonstrates.

## What is solid at this head

Executed, not assumed:

- the intro state machine is enforced at the durable row by
  `UPDATE … WHERE state = ?` with a `rowcount != 1` conflict — a second
  decline/cancel/accept cannot double-apply;
- authorization runs through the accepted R12B kernel for both
  `intro:request` and `message:send`, with `ConfirmationRequired` surfacing as
  HTTP 409 and every denial branch normalized to one uniform
  `collaboration_unavailable` (HTTP 400) — foreign, missing, wrong-state and
  non-participant references are indistinguishable, verified for a third party
  over HTTP;
- no contact data appears in any collaboration DTO; only `display_label`;
- `intro_state` in rich results is derived from the same repository read as the
  collaboration service, so there is no second source of truth, and it flipped
  `available → requested → accepted` in the executed HTTP flow;
- the corpus generation is unchanged across request → accept → message → reply
  (chat cannot force an index rebuild);
- every intro/message DTO carries `untrusted: true`; audit payloads carry ids
  only, never message text;
- `0003` is additive and applies cleanly on both SQLite and (with F3's loader
  fix) PostgreSQL;
- the full suite is green at the exact head.

## Convergence with `R14-COLLABORATION-REVIEW-026B` (PR #117), read after the fact

Read only after the findings above were recorded from this run's probe output.

| | 026B (reading) | this run (execution) |
| --- | --- | --- |
| B1 / B2 / B3 | confirmed | confirmed, incl. live-browser B2 and DB-boundary B3a |
| requester cannot reach `channel_id` | **N1** | **F1** — same conclusion, reached independently |
| cross-author `request_id` collision | **N2** | not found by me; **independently verified by execution** below |
| decline cooldown / unbounded reads / count mismatch | N3 / N4a / N4b | count mismatch independently confirmed (10, not 12) |
| "PostgreSQL byte-parity could not be executed here" | **N4c, open** | **F3 — executed; the backend does not start on any head** |
| `collab.mjs` guest downgrade | — | **F2** |

Two independent runs, different models, different methods, converging on
F1/N1 is the strongest signal in this review: it is a real acceptance blocker,
and it was invisible to a green suite.

**026B's N2, independently verified here by execution.** Bob sends `"hello"`
with `request_id="msg-1"`; Alice then sends `"hello"` with `request_id="msg-1"`
in the same channel:

```
bob message_id  : msg-56734036d2d42ea4e00d2225
alice response  : {'message_id': 'msg-56734036d2d42ea4e00d2225', 'delivered': True}
thread rows     : [('counterpart', 'hello', 'msg-56734036d2d42ea4e00d2225')]
alice row stored: False
different body  : PersistenceConflictError: request_id 'msg-1' was already used for a different request
```

Confirmed exactly: Alice is told `delivered: True` and handed **Bob's**
`message_id`, and her message is never stored. The `collab.message.send`
idempotency hash is `{channel_id, body}` and excludes the author, while
`idempotency_keys` is global on `request_id`. Since the WebMCP schema asks the
*agent* to supply `request_id`, two agents picking `msg-1` is realistic. Adding
`author_user_id` to the hash makes a collision fail closed instead of silently
reporting a foreign message as delivered. I concur that this is cheap to fix
now, and note the same actor-exclusion applies to `collab.intro.respond` and
`collab.intro.cancel`.

## Recommendation

**Concur with `REQUEST_CHANGES`.** Acceptance closure for R14 should cover:

1. **B1** — visible human UI controls, and remove or replace the
   "Introductions unavailable" placeholder;
2. **B2** — a committed same-origin CSRF/session bootstrap that survives
   reload for an authenticated owner, with a browser regression and no harness
   injection;
3. **B3** — one accepted intro ⇒ exactly one channel, enforced at the DB
   boundary (`UNIQUE(intro_id)` on `channels`) *and* made atomic with the
   accept transition, with regressions for the concurrent case (B3b) and the
   lost-write case (B3c);
4. **F1 / 026B-N1** — a participant read path to `channel_id` for an accepted
   intro, regression-tested so B obtains it from `list_requests` rather than
   from A's response;
5. **026B-N2** — include the author in the `message:send` idempotency hash so
   a cross-author key collision fails closed;
6. **F2** — do not let a WebMCP tool mint a guest identity for an
   authenticated visitor.

**F3 is not R14's blocker** and must not be charged to this run; it is reported
separately to the R11/R16 lane. It is, however, release-blocking for R16.

Review input only. Canonical run `R14-COLLABORATION-F5` remains reserved by
`dima2010-anthropic-fable5-7328`; no `REOPEN_CANONICAL` is implied, and no
commit was pushed to PR #116.

## Appendix A — `r14_repro_probe.py`

Reproduces B1, B2 (static), B3a/B3b/B3c, F1, F2. Run from the PR-head
worktree: `python3 r14_repro_probe.py`.

```python
"""R14-COLLABORATION-REPRO-3F1C — executable reproduction probe for PR #116.

Reviewer: parshkov-anthropic-opus5-3f1c (Claude Opus 5). Non-canonical review run.
Target head: a5c093390ea713c5a3cf667260d24c33c2e8fa8d.

Every probe here EXECUTES the shipped code at the reviewed head. No production
file is modified. Where an interleaving is injected to make a race
deterministic, the probe says so in its own output.

Run: python3 r14_repro_probe.py
"""

from __future__ import annotations

import json
import threading
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.persistence.errors import PersistenceConflictError
from src.persistence.models import ChannelRecord
from src.product.server import build_runtime, serve
from src.product.service import LiveProductService
from src.ingestion.service import ShareIntent
from tests.test_product_live import PRES, QUERY_DNA, location, r7_dna
from tests.test_collaboration import two_user_world, request as make_request

REPO = Path(__file__).resolve().parent
RESULTS: list[tuple[str, str, str]] = []


def record(probe: str, verdict: str, detail: str) -> None:
    RESULTS.append((probe, verdict, detail))
    print(f"[{verdict}] {probe}\n        {detail}\n")


# ----------------------------------------------------------------------
# B1 — human/manual UI surface
# ----------------------------------------------------------------------
def probe_b1_ui_surface() -> None:
    html = (REPO / "demo/ui/index.html").read_text("utf-8")
    controls = [t for t in ("intro-request", "collab-panel", "intro-respond",
                            "channel-send", "id=\"collab", "data-collab")
                if t in html]
    stale = "Introductions unavailable" in html
    record(
        "B1 human-UI collaboration controls",
        "REPRODUCED" if not controls else "NOT REPRODUCED",
        f"committed page markup contains no collaboration control "
        f"(matched selectors: {controls or 'none'}); the page's only "
        f"intro-related element still reads 'Introductions unavailable' "
        f"= {stale}. Only <script src=/collab.mjs> is injected, so the "
        f"WebMCP tool surface exists with no human equivalent.",
    )


# ----------------------------------------------------------------------
# B2 — WebMCP CSRF bootstrap
# ----------------------------------------------------------------------
def probe_b2_csrf_bootstrap() -> None:
    hits: dict[str, list[int]] = {}
    for path in sorted(REPO.glob("demo/**/*.mjs")) + sorted(REPO.glob("demo/**/*.html")) \
            + sorted(REPO.glob("src/**/*.py")):
        try:
            text = path.read_text("utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if "__resonance_csrf" in line:
                kind = "ASSIGN" if "__resonance_csrf =" in line or "__resonance_csrf=" in line else "READ"
                hits.setdefault(f"{kind} {path.relative_to(REPO)}", []).append(lineno)
    assigns = [k for k in hits if k.startswith("ASSIGN")]
    record(
        "B2 committed CSRF bootstrap for an authenticated (non-guest) page",
        "REPRODUCED" if not assigns else "NOT REPRODUCED",
        f"`window.__resonance_csrf` occurrences at this head: {hits or 'none'}. "
        f"It is read by demo/ui/collab.mjs:41 and assigned nowhere in the "
        f"repository, so after a reload with an owned (authenticated) session "
        f"`ensureSession()` leaves csrfToken null and every collaboration POST "
        f"is CSRF-rejected. Executed browser confirmation: see probe B2-live.",
    )


# ----------------------------------------------------------------------
# B3 — one accepted intro must mean exactly one channel
# ----------------------------------------------------------------------
def probe_b3_db_boundary() -> None:
    """No interleaving injected: the repository itself accepts two channels."""
    live, identity, product, alice, a_session, bob, b_session = two_user_world()
    intro = make_request(product, bob, b_session, a_session)
    accepted = product.respond_intro(alice.access_token, intro["intro_id"],
                                     accept=True, request_id="acc-1", confirmed=True)
    repo = identity.backend.repo
    second = repo.create_channel(ChannelRecord(channel_id="chan-reviewer-dup",
                                               intro_id=intro["intro_id"],
                                               created_at="2026-09-03T23:30:00Z"))
    rows = [r for r in repo._conn.execute(
        "SELECT channel_id FROM channels WHERE intro_id = ?",
        (intro["intro_id"],)).fetchall()]
    record(
        "B3a durable uniqueness of channels.intro_id (no injection)",
        "REPRODUCED" if len(rows) > 1 else "NOT REPRODUCED",
        f"repository accepted a second channel for one accepted intro without "
        f"error: {[r[0] for r in rows]}. `channels.intro_id` has no UNIQUE "
        f"constraint in 0001_init.sql and 0003_collaboration.sql does not add "
        f"one, so the invariant is not enforced at the DB/repository boundary. "
        f"First channel served to the acceptor was {accepted['channel_id']}; "
        f"`get_channel_by_intro` silently returns only the earliest row, so a "
        f"duplicate hides instead of failing.")


def probe_b3_service_race() -> None:
    """Interleaving INJECTED: two concurrent accepts with the same request_id."""
    live, identity, product, alice, a_session, bob, b_session = two_user_world()
    intro = make_request(product, bob, b_session, a_session)
    repo = identity.backend.repo
    real_lookup = repo.get_channel_by_intro
    barrier = threading.Barrier(2, timeout=10)

    def gated_lookup(intro_id):
        result = real_lookup(intro_id)
        try:  # hold both threads in the check-then-insert window
            barrier.wait()
        except threading.BrokenBarrierError:
            pass
        return result

    repo.get_channel_by_intro = gated_lookup
    out: list[object] = []

    def accept():
        try:
            out.append(product.respond_intro(
                alice.access_token, intro["intro_id"], accept=True,
                request_id="same-key", confirmed=True))
        except Exception as exc:  # noqa: BLE001 - recorded as evidence
            out.append(exc)

    threads = [threading.Thread(target=accept) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
    repo.get_channel_by_intro = real_lookup
    rows = [r[0] for r in repo._conn.execute(
        "SELECT channel_id FROM channels WHERE intro_id = ?",
        (intro["intro_id"],)).fetchall()]
    served = sorted({r.get("channel_id") for r in out if isinstance(r, dict)})
    record(
        "B3b concurrent idempotent accept mints two channels (interleaving INJECTED)",
        "REPRODUCED" if len(rows) > 1 else "NOT REPRODUCED",
        f"two concurrent respond_intro calls with the SAME request_id "
        f"('same-key', so the durable idempotency replay path is taken by one "
        f"of them) produced channel rows {rows} and served channel ids "
        f"{served}. The transition and the channel insert are separate "
        f"transactions and the check-then-insert is unguarded, so the two "
        f"participants can be handed different thread ids for one connection. "
        f"Injection disclosure: a reviewer-side barrier inside "
        f"`get_channel_by_intro` holds both threads in the existing window; "
        f"no production code was changed, and B3a shows the window is only "
        f"reachable because the DB does not enforce uniqueness.")


def probe_b3_lost_channel_write() -> None:
    """No injection: an accepted intro whose channel write did not survive."""
    live, identity, product, alice, a_session, bob, b_session = two_user_world()
    intro = make_request(product, bob, b_session, a_session)
    accepted = product.respond_intro(alice.access_token, intro["intro_id"],
                                     accept=True, request_id="acc-lost", confirmed=True)
    repo = identity.backend.repo
    # Simulate the crash window between the two transactions: the transition
    # committed, the channel insert did not.
    repo._conn.execute("DELETE FROM channels WHERE intro_id = ?",
                       (intro["intro_id"],))
    repo._conn.commit()
    replay = product.respond_intro(alice.access_token, intro["intro_id"],
                                   accept=True, request_id="acc-lost",
                                   confirmed=True)
    fresh_key_error = None
    try:
        product.respond_intro(alice.access_token, intro["intro_id"], accept=True,
                              request_id="acc-different", confirmed=True)
    except Exception as exc:  # noqa: BLE001
        fresh_key_error = f"{type(exc).__name__}: {exc}"
    record(
        "B3c recovery after a lost channel write depends on replaying the exact request_id",
        "REPRODUCED",
        f"with the channel row removed (crash between the two transactions), a "
        f"replay of the ORIGINAL request_id re-creates a channel "
        f"({replay.get('channel_id')}), but any other request_id fails with "
        f"{fresh_key_error} because the intro is no longer 'requested'. "
        f"So recovery is only possible for a client that still holds the exact "
        f"idempotency key; otherwise the connection is accepted forever with no "
        f"reachable channel. Original id was {accepted['channel_id']}.")


# ----------------------------------------------------------------------
# F1 (new) — the requester has no read path to the channel
# ----------------------------------------------------------------------
class Client:
    def __init__(self, base: str, origin: str):
        self.base, self.origin = base, origin
        self.cookie = self.csrf = None

    def call(self, method, path, body=None):
        headers = {"Content-Type": "application/json", "Origin": self.origin}
        if self.cookie:
            headers["Cookie"] = self.cookie
        if self.csrf:
            headers["X-Resonance-CSRF"] = self.csrf
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = Request(self.base + path, data=data, headers=headers, method=method)
        with urlopen(req, timeout=10) as response:
            set_cookie = response.headers.get("Set-Cookie")
            if set_cookie:
                morsel = SimpleCookie(set_cookie).get("resonance_token")
                if morsel is not None:
                    self.cookie = f"resonance_token={morsel.value}"
            return json.loads(response.read().decode("utf-8"))

    def guest(self):
        payload = self.call("POST", "/api/product/guest", {})
        self.csrf = payload["csrf_token"]
        return payload

    def share(self, source, thought_id, loc=None, intent=None):
        prepared = self.call("POST", "/api/product/prepare", {
            "candidate": r7_dna(source, thought_id),
            "presentation": dict(PRES),
            "coarse_location": dict(loc) if loc else None,
            "share_intent": intent or {"share_display_profile": True,
                                       "share_coarse_location": bool(loc)}})
        preview = self.call("GET", f"/api/product/preview?draft_id={prepared['draft_id']}")
        self.call("POST", "/api/product/share", {
            "draft_id": prepared["draft_id"],
            "confirmation_token": preview["confirmation_token"], "confirmed": True})
        return prepared["session_id"]


def probe_f1_requester_cannot_reach_channel() -> None:
    probe = build_runtime(":memory:", allowed_origins=frozenset({"pending"}))
    server = serve("127.0.0.1", 0, runtime=probe)
    host, port = server.server_address[:2]
    origin = f"http://{host}:{port}"
    server.RequestHandlerClass.runtime = build_runtime(
        ":memory:", allowed_origins=frozenset({origin}))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        alice = Client(origin, origin); alice.guest()
        a_session = alice.share("ses-gabe-warehouse", "thought-f1-alice",
                                loc=location("R"))
        alice.call("POST", "/api/product/consent", {
            "session_id": a_session,
            "choices": {"share_thought_dna": True, "share_display_profile": True,
                        "share_coarse_location": True, "allow_intro_requests": True},
            "confirmed": True})
        bob = Client(origin, origin); bob.guest()
        b_session = bob.share(QUERY_DNA, "thought-f1-bob")
        disc = bob.call("GET", f"/api/product/discover?session_id={b_session}&k=20")
        assert a_session in [m["session_id"] for m in disc["matches"]], "no match to introduce over"
        intro = bob.call("POST", "/api/product/intro/request", {
            "from_session_id": b_session, "target_session_id": a_session,
            "message": "compare mitigations?", "request_id": "f1-req",
            "confirmed": True})
        incoming = alice.call("GET", "/api/product/intro/list")["incoming"]
        accepted = alice.call("POST", "/api/product/intro/respond", {
            "intro_id": incoming[0]["intro_id"], "accept": True,
            "request_id": "f1-acc", "confirmed": True})
        channel = accepted["channel_id"]

        # Every GET the product exposes, as the REQUESTER, after acceptance.
        reads = {
            "/api/product/state": "GET",
            "/api/product/sessions": "GET",
            "/api/product/intro/list": "GET",
            f"/api/product/discover?session_id={b_session}&k=20": "GET",
            f"/api/product/rich_discover?session_id={b_session}&k=20": "GET",
        }
        leaks, dump = [], {}
        for path in reads:
            try:
                payload = bob.call("GET", path)
            except HTTPError as exc:
                payload = {"http_error": exc.code}
            dump[path] = payload
            if channel in json.dumps(payload):
                leaks.append(path)
        bob_state = bob.call("GET", "/api/product/intro/list")["outgoing"][0]
        send_error = None
        try:
            bob.call("POST", "/api/product/channel/send", {
                "channel_id": "", "body": "hello", "request_id": "f1-m",
                "confirmed": True})
        except HTTPError as exc:
            send_error = f"HTTP {exc.code} {json.loads(exc.read()).get('error')}"
        record(
            "F1 (new) requester has no read path to the accepted channel id",
            "REPRODUCED" if not leaks else "NOT REPRODUCED",
            f"after acceptance the requester's outgoing intro reads "
            f"{ {k: v for k, v in bob_state.items() if k in ('state', 'intro_id')} } "
            f"with keys {sorted(bob_state)} — no channel_id. None of the "
            f"product's authenticated GET endpoints returns it to the "
            f"requester (checked {sorted(reads)}; leaks={leaks or 'none'}), and "
            f"`channel_id` is emitted exactly once, in the ACCEPTOR's "
            f"respond_intro response. Sending without it fails: {send_error}. "
            f"Channel ids are opaque 24-hex tokens by design, so the requester "
            f"cannot derive it. In tests the id crosses between the two users "
            f"only because a single in-process test body holds both "
            f"(tests/test_collaboration.py:68, "
            f"tests/test_product_http.py `channel = accepted['channel_id']`); "
            f"over HTTP there is no such path, so the mission's "
            f"'B messages through the tool' step is not reachable by a real "
            f"requester. The acceptor loses it on reload for the same reason.")
    finally:
        server.shutdown()
        server.server_close()


# ----------------------------------------------------------------------
# F2 (new) — the WebMCP module mints a guest session for a logged-in user
# ----------------------------------------------------------------------
def probe_f2_guest_downgrade() -> None:
    text = (REPO / "demo/ui/collab.mjs").read_text("utf-8")
    guest_branch = "/api/product/guest" in text and "owned_sessions" in text
    record(
        "F2 (new) collab.mjs mints a guest identity for an authenticated user with no shared sessions",
        "REPRODUCED (static)" if guest_branch else "NOT REPRODUCED",
        "demo/ui/collab.mjs:29-43 `ensureSession()` branches only on "
        "`state.owned_sessions.length`, not on whether the visitor is already "
        "authenticated. A registered user who has not yet shared a session "
        "therefore has POST /api/product/guest called on their behalf by a "
        "WebMCP tool invocation, which issues a new guest token/cookie for the "
        "origin. That is an unrequested identity change performed by an agent "
        "tool, and it is the same branch that hides B2 during guest-only "
        "manual testing. Not executed in a browser here because the same code "
        "path is unreachable until B2 is fixed; flagged as a code-path finding "
        "for the revision, not as executed evidence.")


if __name__ == "__main__":
    probe_b1_ui_surface()
    probe_b2_csrf_bootstrap()
    probe_b3_db_boundary()
    probe_b3_service_race()
    probe_b3_lost_channel_write()
    probe_f1_requester_cannot_reach_channel()
    probe_f2_guest_downgrade()
    print("=" * 72)
    for probe, verdict, _ in RESULTS:
        print(f"{verdict:22} {probe}")
```

## Appendix B — `r14_browser_probe.py`

B2 in a real browser. Run from the PR-head worktree after
`pip install playwright`: `python3 r14_browser_probe.py`.

```python
"""B2 live-browser confirmation — R14-COLLABORATION-REPRO-3F1C.

Loads the real live-product page in headless Chromium as a REGISTERED user who
already owns a shared session, reloads (so nothing is left in the JS context),
and drives the committed demo/ui/collab.mjs tool implementations directly.

No token is injected by this harness: that is the point of the probe.
"""

from __future__ import annotations

import json
import threading

from playwright.sync_api import sync_playwright

from src.product.server import build_runtime, serve
from tests.test_product_live import PRES, QUERY_DNA, r7_dna

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


def main() -> None:
    boot = serve("127.0.0.1", 0,
                 runtime=build_runtime(":memory:", allowed_origins=frozenset({"pending"})))
    host, port = boot.server_address[:2]
    origin = f"http://{host}:{port}"
    boot.RequestHandlerClass.runtime = build_runtime(
        ":memory:", allowed_origins=frozenset({origin}))
    threading.Thread(target=boot.serve_forever, daemon=True).start()

    dna = json.dumps(r7_dna(QUERY_DNA, "thought-browser-b2"))
    pres = json.dumps(dict(PRES))
    report: dict[str, object] = {"origin": origin, "chromium": CHROME}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=CHROME, headless=True,
                args=["--enable-features=WebMCP"])
            page = browser.new_page()
            page.goto(origin + "/", wait_until="domcontentloaded")
            report["webmcp_available"] = page.evaluate(
                "() => Boolean((document.modelContext || navigator.modelContext)?.registerTool)")
            report["ua"] = page.evaluate("() => navigator.userAgent")

            # Register a real (non-guest) account and share one session, using
            # the CSRF token from the registration response — the normal page
            # flow. Nothing is stored on `window`.
            setup = page.evaluate(
                """async ([dna, pres]) => {
                  const post = async (path, body, csrf) => {
                    const headers = {"Content-Type": "application/json"};
                    if (csrf) headers["X-Resonance-CSRF"] = csrf;
                    const r = await fetch(path, {method: "POST", credentials: "same-origin",
                                                 headers, body: JSON.stringify(body)});
                    return {ok: r.ok, status: r.status, payload: await r.json()};
                  };
                  const reg = await post("/api/product/register", {display_label: "Browser Reviewer"});
                  const csrf = reg.payload.csrf_token;
                  const prep = await post("/api/product/prepare", {
                    candidate: JSON.parse(dna), presentation: JSON.parse(pres),
                    coarse_location: null,
                    share_intent: {share_display_profile: true, share_coarse_location: false},
                  }, csrf);
                  const prev = await fetch(`/api/product/preview?draft_id=${prep.payload.draft_id}`,
                                           {credentials: "same-origin"}).then(r => r.json());
                  const shared = await post("/api/product/share", {
                    draft_id: prep.payload.draft_id,
                    confirmation_token: prev.confirmation_token, confirmed: true}, csrf);
                  return {user_id: reg.payload.user_id, shared: shared.payload.discoverable === true};
                }""",
                [dna, pres])
            report["setup"] = setup

            # Reload: an authenticated visitor returning to the page. The
            # committed page never restores a CSRF token.
            page.reload(wait_until="domcontentloaded")
            report["owned_sessions_after_reload"] = page.evaluate(
                """async () => (await fetch("/api/product/state", {credentials: "same-origin"})
                                  .then(r => r.json())).owned_sessions.length""")
            report["window_csrf_after_reload"] = page.evaluate(
                "() => (typeof window.__resonance_csrf === 'undefined') ? 'undefined' : String(window.__resonance_csrf)")
            report["collab_ui_controls_in_dom"] = page.evaluate(
                """() => document.querySelectorAll(
                     '[id*=intro i],[id*=collab i],[data-collab],button[data-intro]').length""")
            report["intro_unavailable_text_present"] = page.evaluate(
                "() => document.body.innerText.includes('Introductions unavailable')")

            # Drive the committed tool implementations. Read first, then write.
            report["read_tool"] = page.evaluate(
                """async () => {
                     const m = await import("/collab.mjs");
                     const tool = m.tools.find(t => t.name === "resonance_list_requests");
                     try { return {ok: true, result: await tool.execute({})}; }
                     catch (e) { return {ok: false, error: String(e)}; }
                   }""")
            report["write_tool"] = page.evaluate(
                """async () => {
                     const m = await import("/collab.mjs");
                     const tool = m.tools.find(t => t.name === "resonance_request_intro");
                     try {
                       return {ok: true, result: await tool.execute({
                         from_session_id: "ses-does-not-matter",
                         target_session_id: "ses-also-not",
                         message: "reviewer probe", request_id: "browser-probe",
                         confirm: true})};
                     } catch (e) { return {ok: false, error: String(e)}; }
                   }""")
            report["status_line"] = page.evaluate(
                "() => document.getElementById('collab-status')?.textContent || null")
            browser.close()
    finally:
        boot.shutdown()
        boot.server_close()

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
```

Output obtained in this container:

```json
{
  "origin": "http://127.0.0.1:36241",
  "chromium": "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  "webmcp_available": false,
  "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/141.0.0.0 Safari/537.36",
  "setup": {"user_id": "person-87550832b15eeb23", "shared": true},
  "owned_sessions_after_reload": 1,
  "window_csrf_after_reload": "undefined",
  "collab_ui_controls_in_dom": 1,
  "intro_unavailable_text_present": true,
  "read_tool": {"ok": true, "result": {"incoming": [], "outgoing": []}},
  "write_tool": {"ok": false, "error": "Error: csrf_rejected: missing CSRF proof"},
  "status_line": "Collab · WebMCP unavailable"
}
```

`collab_ui_controls_in_dom: 1` is the `#collab-status` span that
`collab.mjs` injects for its own status text, not a control.

## Appendix C — `r14_postgres_probe.py`

F3. Requires a running PostgreSQL and `pip install "psycopg[binary]"`.
The cluster used here was created with:

```bash
su -s /bin/bash postgres -c "initdb -D \$PGDATA -U postgres --auth=trust"
su -s /bin/bash postgres -c "pg_ctl -D \$PGDATA -o '-p 55432 -k /tmp -c listen_addresses=127.0.0.1' -l \$PGDATA/log start"
psql -h 127.0.0.1 -p 55432 -U postgres -c "CREATE DATABASE r14pg"
```

```python
"""Live-PostgreSQL probe — R14-COLLABORATION-REPRO-3F1C.

The repository's live-PostgreSQL smoke test is skipped unless
RESONANCE_TEST_POSTGRES_URL is set, so the PostgreSQL store has never been
executed in CI. This container has PostgreSQL 16.13, so it can be.

Stage 1: run the shipped code unchanged and report what happens.
Stage 2: apply ONE reviewer-side patch (strip `--` comments before the naive
         `;` split in PostgresRepository._execute_script) and re-run, to
         separate "loader bug" from "backend unfinished".
Stage 3: with stage 2 in place, exercise R14's new collaboration store methods
         on live PostgreSQL — the 170 lines added to postgres_store.py by
         PR #116 that no test has ever executed.
"""

from __future__ import annotations

import os
import re
import sys
import traceback

from src.persistence.factory import open_repository
from src.persistence.models import ChannelRecord, IntroRecord, MessageRecord
from src.persistence.postgres_store import PostgresRepository

DSN = os.environ["RESONANCE_TEST_POSTGRES_URL"]


def head() -> str:
    import subprocess
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                          text=True).stdout.strip()


def stage1() -> None:
    print("== stage 1: shipped code, unmodified ==")
    try:
        repo = open_repository(DSN)
        print("   migrate() ->", repo.migrate())
        print("   RESULT: PostgreSQL migration SUCCEEDED")
    except Exception:
        line = traceback.format_exc().strip().splitlines()[-1]
        print("   RESULT: PostgreSQL migration FAILED ->", line)
        print("   cause: ops/migrations/0001_init.sql line 2 is the comment")
        print("          '-- Derived from superseded R11 PR #95 (Grok 4.6);"
              " preserved verbatim in shape'")
        print("          and PostgresRepository._execute_script splits the file"
              " on ';' without")
        print("          stripping comments, so the comment tail is submitted"
              " as a statement.")


_COMMENT = re.compile(r"--[^\n]*")


def patched_execute_script(self, sql: str) -> None:
    for statement in _COMMENT.sub("", sql).split(";"):
        statement = statement.strip()
        if statement:
            self._execute(statement)


def stage2() -> object:
    print("\n== stage 2: reviewer patch (strip `--` comments before split) ==")
    PostgresRepository._execute_script = patched_execute_script
    repo = open_repository(DSN)
    print("   migrate() ->", repo.migrate())
    tables = [r["table_name"] for r in repo._fetchall_map(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' ORDER BY table_name")]
    print("   tables:", tables)
    cols = [r["column_name"] for r in repo._fetchall_map(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'intros' ORDER BY column_name")]
    print("   intros columns (0003 applied):", cols)
    uniq = repo._fetchall_map(
        "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'channels'")
    print("   channels indexes:", [(r["indexname"], r["indexdef"]) for r in uniq])
    return repo


def stage3(repo) -> None:
    print("\n== stage 3: R14 collaboration store methods on live PostgreSQL ==")
    repo.create_user_record if hasattr(repo, "create_user_record") else None
    intro = IntroRecord(intro_id="intro-pg-1", from_user_id="person-a",
                        to_user_id="person-b", from_session_id="ses-a",
                        to_session_id="ses-b", state="requested",
                        message="live postgres probe",
                        created_at="2026-09-03T23:40:00Z",
                        updated_at="2026-09-03T23:40:00Z")
    print("   create_intro ->", repo.create_intro(intro).intro_id)
    print("   get_intro    ->", repo.get_intro("intro-pg-1").state)
    print("   list_for_user->", [i.intro_id for i in repo.list_intros_for_user("person-b")])
    print("   latest_between->", repo.latest_intro_between("person-a", "person-b").state)
    moved = repo.transition_intro("intro-pg-1", from_state="requested",
                                  to_state="accepted",
                                  timestamp_field="accepted_at",
                                  now="2026-09-03T23:41:00Z")
    print("   transition   ->", moved.state, moved.accepted_at)
    print("   accepted_pairs->", repo.accepted_user_pairs())
    first = repo.create_channel(ChannelRecord(channel_id="chan-pg-1",
                                              intro_id="intro-pg-1",
                                              created_at="2026-09-03T23:41:01Z"))
    print("   create_channel->", first.channel_id)
    dup_error = None
    try:
        repo.create_channel(ChannelRecord(channel_id="chan-pg-2",
                                          intro_id="intro-pg-1",
                                          created_at="2026-09-03T23:41:02Z"))
    except Exception as exc:  # noqa: BLE001
        dup_error = f"{type(exc).__name__}: {exc}"
    rows = [r["channel_id"] for r in repo._fetchall_map(
        "SELECT channel_id FROM channels WHERE intro_id = 'intro-pg-1' "
        "ORDER BY channel_id")]
    print("   second channel for the same intro:",
          dup_error or "ACCEPTED (no uniqueness)", "->", rows)
    repo.add_message(MessageRecord(message_id="msg-pg-1", channel_id="chan-pg-1",
                                   author_user_id="person-a", body="hello pg",
                                   created_at="2026-09-03T23:41:03Z"))
    print("   list_messages->", [(m.message_id, m.body)
                                 for m in repo.list_messages("chan-pg-1")])
    print("   get_channel_by_intro->", repo.get_channel_by_intro("intro-pg-1").channel_id)
    print("\n   VERDICT: with the one-line loader fix, every R14 collaboration")
    print("            store method works on live PostgreSQL 16.13, and the")
    print("            missing channels.intro_id uniqueness reproduces on")
    print("            PostgreSQL exactly as on SQLite.")


if __name__ == "__main__":
    print(f"head: {head()}   dsn: {DSN.split('@')[-1]}")
    stage1()
    try:
        repo = stage2()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
    stage3(repo)
```

---

# Addendum — re-verification at revised head `3397e96`

`dima2010-anthropic-fable5-7328` pushed the R14 revision as
`3397e96094a577ed30ab90c6d070717863d0e6d8` ("R14 revision: close the three
review blockers"). As promised in the `SUBMIT` above, the whole battery was
re-run against the new head by the same method. Same reviewer, same runtime.

Everything in the sections above pertains to `a5c0933` and is superseded by
what follows.

## Suite at the revised head

| Run | Result |
| --- | --- |
| full suite, `python3 -m pytest -q` | **360 passed, 2 skipped, 12 subtests passed** in 612.51 s, exit 0 |
| `tests/test_collaboration.py` collected | 11 (was 10) |

Two regression tests were added (`test_accept_is_atomic_one_channel_per_intro`,
`test_session_bootstrap_csrf_survives_reload_without_injection`).

Accounting for the run-to-run difference, so the comparison is honest: the
second skip is **not** caused by the revision. I installed `psycopg` in this
container between the two runs (for §F3), which flips
`test_postgres_dsn_never_silently_falls_back_to_sqlite` from passing to
skipping. 359 passing + 2 new tests − 1 newly-skipping test = 360. Consistent.

## Verdicts

| Item | At `a5c0933` | At `3397e96` |
| --- | --- | --- |
| B1 human UI | reproduced | **partially closed** — see below |
| B2 CSRF bootstrap | reproduced | **CLOSED** |
| B3 one intro ⇒ one channel | reproduced (3 ways) | **CLOSED**, both backends |
| F1 requester read path | reproduced | **CLOSED** |
| F2 guest downgrade | reproduced (static) | **CLOSED** |
| 026B-N2 author collision | confirmed | **STILL OPEN** |
| F3 PostgreSQL loader | reproduced (not R14's) | **unchanged, still not R14's** |
| F4 multi-tab stranding | — | **NEW — regression from the B2 fix** |

### B2 — CLOSED

`demo/ui/session.mjs` persists the CSRF token in `sessionStorage` at issue
time and, when a cookie authenticates but the per-tab token is absent, mints a
fresh one for the same subject via a new `POST /api/product/rotate`.

Executed in headless Chromium with no injected token: with an owned session,
`sessionStorage.clear()` then reload → a token is present again and the
committed write tool no longer returns `csrf_rejected` (it reaches business
validation instead). The two-user flow then completes through real UI clicks
(below), which is the strongest form of this evidence.

I also checked that the new endpoint is not itself a CSRF hole, since it sits
in the pre-CSRF block of `_route_post` and takes only the cookie:

- `POST /api/product/rotate` with **no** cookie and a foreign `Origin` →
  `HTTP 401 authentication_failed`;
- the session cookie is `HttpOnly; SameSite=Strict; Path=/`, so a cross-site
  page cannot cause it to be sent, and `document.cookie` reads empty in the
  live page.

So the bootstrap is sound as a CSRF design. Its problem is different — F4.

### B3 — CLOSED, on both backends

`0003` now adds `CREATE UNIQUE INDEX idx_channels_intro ON channels(intro_id)`,
the channel id is deterministic (`chan-` + `sha256(intro_id)[:24]`), and
`accept_intro` performs the transition and the `INSERT OR IGNORE` in **one**
transaction. Executed:

- a second channel row for one accepted intro is now rejected
  (`PersistenceConflictError`); rows stay at exactly one;
- two concurrent accepts with the same `request_id` converge — one channel row,
  one served id, no errors (at `a5c0933` this produced two rows and two ids);
- on **live PostgreSQL 16.13**, `idx_channels_intro` is present as
  `CREATE UNIQUE INDEX … USING btree (intro_id)`, `accept_intro` returns
  `accepted` + the deterministic channel, a duplicate insert is rejected, and
  relay messages round-trip. (The F3 loader patch is applied first, since F3 is
  still present and is not R14's defect. A replay of `accept_intro` *without*
  an idempotency key correctly raises "not in state 'requested'" — that is the
  CAS working, not a defect; convergence is via the key, proven on SQLite.)

B3c is no longer reachable: with one transaction there is no window between the
transition and the channel insert. Forcing the state by deleting the row shows
the intro DTO simply omits `channel_id` and cannot self-heal — worth a thought
for backup/restore, but not a live defect.

### F1 — CLOSED

`_intro_dto` now attaches `channel_id` when `state == "accepted"`. Executed:
the requester's **own** `list_requests` returns the same channel id the
acceptor received, and the requester sent and read back a message without ever
touching the acceptor's response. A non-participant is still denied with the
uniform error. The fix also surfaces in the UI — B's panel shows
"accepted … Open channel".

### F2 — CLOSED

The `owned_sessions.length` guest branch is gone; `session.mjs` rotates for the
authenticated subject instead of minting a guest. No WebMCP tool call can now
change who the visitor is.

### B1 — partially closed

**What is genuinely delivered**, verified by real clicks in headless Chromium
across two browser contexts (two separate cookie jars), not by reading:

- `#collab-panel` renders on load: "Collaboration / Incoming / Outgoing".
- After B requests an intro, A's panel shows the request with the requester's
  pseudonym and message plus **Accept** / **Decline** buttons.
- Clicking **Accept** transitions the row to "accepted" and swaps in
  **Open channel**; B's panel independently shows "accepted … Open channel".
- Clicking **Open channel** renders a thread view with a text input and a
  **Send** button; A typed and sent a message through the UI, and B — in a
  separate browser context — opened the channel and read the same message.

That is a real human surface for respond → accept → message → read, and the
"direct HTTP is not a UI" objection is answered for those steps.

**What is still missing — a human cannot start an intro.** The only initiation
control is built by `attachMatchCardButtons`, which reads

```js
const fromSession = document.body.dataset.querySession || window.__query_session;
if (!fromSession) continue;                       // demo/ui/collab_ui.mjs:185-186
```

Neither name is set anywhere in the repository — `collab_ui.mjs:185` is the
only occurrence of either — and both read `null` in the live page. So the guard
always continues and the "Request intro" button is **never created**:
`.collab-request-btn` count is 0, including after forcing `init()` again with
discovery already run. In my probe the requester had to initiate through the
WebMCP tool, which is the only working path.

This is the **same failure mode as B2**: a module reads a page global that
nothing ever assigns. It also shows why the new test does not catch it — 
`test_ui_is_served_with_live_injection` asserts `assertIn("Request intro", ui)`
against the *served module source*. A source-substring assertion cannot
distinguish "the control exists" from "the control is unreachable"; only
rendering the page can.

Secondary: the accepted R9 placeholder still reads "Introductions unavailable /
Not exposed by the accepted R8 MCP", now displayed on the same page as a
working Collaboration panel. Contradictory to a judge or pilot user.

Suggested closure: set `document.body.dataset.querySession` (or expose the
selected query session through the same module boundary) wherever the page
learns its query session, add a DOM-level regression that asserts a rendered
`.collab-request-btn` after a discovery, and remove or rewrite the placeholder.

### 026B-N2 — STILL OPEN

Re-executed at the new head: Bob sends `"hello"` with `request_id="msg-1"`,
then Alice sends `"hello"` with `request_id="msg-1"` in the same channel →
Alice receives `delivered: True` carrying **Bob's** `message_id`, and the
thread holds only Bob's row. The `collab.message.send` hash is still
`{channel_id, body}` with no `author_user_id`, and `idempotency_keys` remains
global on `request_id`. Unchanged from `a5c0933`.

### F4 (new) — opening a second tab strands the first

The B2 fix introduces a regression. `sessionStorage` is **per tab**, while the
cookie is per browser context, and `rotate_session` *revokes* the previous auth
session (`src/identity/service.py:183-186`).

Executed in one browser context, two tabs, with the network log captured:

1. Tab 1 bootstraps, shares a session, and a valid write succeeds (`"OK"`).
2. Tab 2 is opened. Its `session.mjs` finds no per-tab token, sees an owned
   session, and calls `POST /api/product/rotate` → **200** (visible in tab 2's
   request log, alongside `/api/product/state` and `/intro/list`).
3. Tab 1 now repeats the **same valid write**:
   `Error: csrf_rejected: invalid CSRF proof`. A second attempt fails
   identically — there is no self-healing, because `ensureSession()` returns
   `readStored(CSRF_KEY)` immediately without validating it.
4. Tab 1's reads still return **200**, so the tab looks perfectly healthy while
   every write silently fails.

HTTP-level confirmation, one variable at a time:

| request | result |
| --- | --- |
| new cookie + **old** CSRF | **403 `csrf_rejected`** |
| new cookie + new CSRF | 200 |
| old cookie (read or write) | 401 `authentication_failed` — prior token revoked |
| repeated rotate | 200, new CSRF each time |

Impact: a second tab, a restored browser session, or any concurrent client of
the same subject (a remote-MCP bearer session included, since rotation revokes
the *auth session*) breaks the others' writes until the user clears per-tab
storage. The author's new test cannot see it — it exercises a single client
whose cookie and token are updated together, never two concurrent clients of
one subject.

Suggested closure: on a `csrf_rejected` response, clear the stored token and
re-bootstrap once before failing; and/or don't rotate when another tab already
holds a valid token (share it via `localStorage` and rotate only when genuinely
absent, or add a read-only "current CSRF" endpoint that does not revoke the
access token). A regression with two concurrent clients of one subject would
have caught this and should ship with the fix.

## Revised recommendation

The revision closes **B2, B3, F1 and F2** — verified by execution, on both
backends for B3 — and delivers a genuine human surface for accepting and
messaging. That is substantial, and the atomic-accept design (deterministic
channel id + unique index + single transaction) is the right fix rather than a
patch over the symptom.

Remaining before acceptance:

1. **B1a** — a human cannot initiate an intro; `querySession` is never set, so
   the only initiation control never renders. This blocks the human half of
   #86's acceptance scenario.
2. **F4** — opening a second tab breaks writes in the first, silently and
   permanently. Introduced by the B2 fix.
3. **026B-N2** — cross-author `request_id` collision reports a foreign message
   as delivered and drops the real one.
4. Cosmetic but judge-visible: the "Introductions unavailable" placeholder.

`F3` remains a maintainer/R11 item, reported on #88, and is still not R14's.

Still review input only. Canonical run `R14-COLLABORATION-F5` remains reserved
by `dima2010-anthropic-fable5-7328`; no `REOPEN_CANONICAL` is implied, and
nothing was pushed to PR #116.

## Appendix D — re-verification probes

Run from a worktree at `3397e96`. Sources of the four probes used above —
`r14_reverify.py` (B3/F1/N2), `r14_b1_probe.py` + `r14_b1_respond.py`
(B1 depth and the UI accept/message loop), `two_tab.py` (F4),
`rotate_semantics.py` (rotate semantics at HTTP level), `pg_reverify.py`
(B3 on live PostgreSQL) — follow the same shape as Appendices A–C: they import
the shipped modules, drive the committed browser code, and modify no
production file. The single reviewer-side patch, applied only in
`pg_reverify.py`, is the F3 comment-stripping loader fix, and it is disclosed
in that probe's own output.

---

# Addendum 2 — verified patches, and why B1a is a pre-existing R13 defect

Written after the maintainer's `REVIEW_INPUT_DELTA` made closure
`B1+B2+B3+N1+N2`, and after PR #118 (this artifact's first two sections) was
merged as `d2f0d24`. With the Devpost deadline at Sep 4 01:00 PT, the useful
contribution stopped being "report" and became "hand over something that runs".

Everything below was applied to a worktree at `3397e96`, executed, and checked
both ways: each patch fails its regression when reverted and passes with it.
The author's 11 collaboration tests stay green with all three applied. Nothing
was pushed to PR #116.

## The live product page never boots for a human (pre-existing, not R14's)

While trying to demonstrate a fix for B1a I could not get the control to render,
and the reason turned out to be underneath R14 entirely.

Loading `/` from `src/product/server.py` in headless Chromium leaves the page on
its placeholders forever — `"Checking consent"`, `"Loading accepted context…"`,
`"Preparing the shared Thought DNA."`, `match cards in DOM: 0` — with two
independent causes:

1. **`/api/config` and `/api/context` 404 on the live server.** `app.mjs`
   `boot()` fetches both and throws `"Presentation context is unavailable"` if
   either is not ok, so `renderContext`, the source buttons and `loadSource`
   never run. Those routes exist only in the R9 demo server
   (`demo/ui/server.py:206`).
2. **The live server's CSP refuses the live-mode marker it injects itself.**
   `src/product/server.py:111-112` sends `default-src 'self'; frame-ancestors
   'none'` with no inline allowance, while line 223 injects
   `<script>window.RESONANCE_MODE = "live";</script>`. Chromium logs *Refused to
   execute inline script…* and `window.RESONANCE_MODE` evaluates to **`null`**
   on the live origin.

`test_ui_is_served_with_live_injection` asserts the string
`window.RESONANCE_MODE = "live"` appears in the served HTML. It does; it just
never executes. That is the **third** instance in this review of a
served-source assertion standing in for a behavioural one — the same shape as
B1's `assertIn("Request intro", ui)` and B2's page-global assumption.

**Attribution.** Verified on accepted `main` @ `d2f0d24` (R13 + R13B merged),
with no R14 code involved: same two 404s, same CSP refusal,
`window.RESONANCE_MODE` null, zero match cards. This is an **R13
page-integration defect**, reported separately on #88, and explicitly not
charged to R14.

**Consequence for B1a.** R14's "Request intro" control attaches to
`.match-card[data-session-id]`, so:

- on the **live server** the collaboration modules load but no cards exist;
- on the **R9 demo server** cards exist but that server injects none of
  `session.mjs` / `collab.mjs` / `collab_ui.mjs`, so there is no panel at all.

`.collab-request-btn` therefore cannot render anywhere, on any head, with or
without the `querySession` fix. The candidate patch below is still the right
change — it removes a guard that can never pass — but it cannot be *demonstrated*
until the page boots.

Against #88's matrix this independently sinks item 7 (human UI shows the same
result and map/cards), item 32 (judge flow from the public URL) and item 36
(independent reviewer completes the flow from repo + URL). Suggested fixes are on
#88: route the presentation context from the live server, and carry live mode in
a `data-` attribute rather than an inline script under a strict CSP.

## Patch 1 — N2, author-bound message idempotency

```diff
--- a/src/collaboration/service.py
+++ b/src/collaboration/service.py
@@
+        # The author is part of the idempotency identity: a request_id chosen by
+        # another participant's agent must not replay their message as ours.
         key = _sha_key("collab.message.send", request_id,
-                       {"channel_id": channel_id, "body": body})
+                       {"author": actor.user_id,
+                        "channel_id": channel_id, "body": body})
```

Execution corrected my first assumption here, which is worth recording. I
expected both messages to persist; they do not, because `idempotency_keys` is
**global** on `request_id` (accepted R11/R12C design). What the patch actually
does is convert silent data loss into a visible
`PersistenceConflictError: request_id 'msg-1' was already used for a different
request`. That is precisely the maintainer's bar — "fails closed or remains
correctly subject-scoped" — and it is R14-sized. Making both messages persist
requires namespacing the idempotency keyspace per subject, an R11-level change
that should not be attempted under deadline.

Same-author replay remains idempotent (one row, same `message_id`) — verified.

## Patch 2 — F4, re-bootstrap once on a rejected CSRF proof

```diff
--- a/demo/ui/session.mjs
+++ b/demo/ui/session.mjs
-async function apiFetch(method, path, body) {
+async function sendOnce(method, path, body) {
   const csrf = await ensureSession();
   ...
   const payload = await response.json().catch(() => ({}));
+  return {response, payload};
+}
+
+async function apiFetch(method, path, body) {
+  let {response, payload} = await sendOnce(method, path, body);
+  if (response.status === 403 && payload.error === "csrf_rejected") {
+    // Another tab rotated this subject's session, so the token cached for THIS
+    // tab is stale. Drop it, re-bootstrap once, and retry before failing.
+    try { sessionStorage.removeItem(CSRF_KEY); } catch { /* private mode */ }
+    window.__resonance_csrf = null;
+    bootstrapPromise = null;
+    ({response, payload} = await sendOnce(method, path, body));
+  }
   if (!response.ok) {
```

Two-tab browser test, same script as the F4 finding: tab 1's write after tab 2
bootstraps goes from `Error: csrf_rejected: invalid CSRF proof` on both attempts
to **`OK`** on both. The tab self-heals instead of being silently write-dead.

## Patch 3 — B1a candidate (correct, not yet demonstrable)

Replaces a guard on a global nothing assigns with the viewer's own session,
resolved from the authenticated owned-sessions surface. The server already
enforces requester ownership via `consent_for()`, so this matches the existing
authorization model rather than widening it.

```diff
--- a/demo/ui/collab_ui.mjs
+++ b/demo/ui/collab_ui.mjs
+let ownSessionPromise = null;
+
+async function ownQuerySession() {
+  const explicit = document.body.dataset.querySession || window.__query_session;
+  if (explicit) return explicit;
+  if (!ownSessionPromise) {
+    ownSessionPromise = apiFetch("GET", "/api/product/sessions")
+      .then((data) => (data.sessions || [])[0]?.session_id || null)
+      .catch(() => null);
+  }
+  return ownSessionPromise;
+}
+
 function attachMatchCardButtons() {
   for (const card of document.querySelectorAll(".match-card[data-session-id]")) {
     if (card.querySelector(".collab-request-btn")) continue;
     const target = card.dataset.sessionId;
-    const fromSession = document.body.dataset.querySession || window.__query_session;
-    if (!fromSession) continue;
     ...
-      try { await requestIntro(fromSession, target, message); }
-      catch (error) { showError(error.message); }
+      try {
+        const fromSession = await ownQuerySession();
+        if (!fromSession) {
+          showError("Share one of your own ideas first to request an intro.");
+          return;
+        }
+        await requestIntro(fromSession, target, message);
+      } catch (error) { showError(error.message); }
```

Labelled honestly: **not verified end-to-end**, because no match card exists on
the live origin to attach to. It should be landed together with the #88 page fix
and a DOM regression asserting a rendered `.collab-request-btn`.

## Regression module handed to the canonical author

`tests/test_r14_reviewer_regressions.py` — 3 tests, ~20 s, passes with Patches 1
and 2 applied; the collision test fails at its assertion with Patch 1 reverted.

```python
"""Reviewer regressions for the two open R14 blockers (N2 and the F4 class)."""

from __future__ import annotations

import unittest

from tests.test_collaboration import request as make_request, two_user_world


class MessageIdempotencyIsAuthorScoped(unittest.TestCase):
    def setUp(self):
        (self.live, self.identity, self.product, self.alice, self.a_session,
         self.bob, self.b_session) = two_user_world()
        intro = make_request(self.product, self.bob, self.b_session, self.a_session)
        accepted = self.product.respond_intro(
            self.alice.access_token, intro["intro_id"], accept=True,
            request_id="acc", confirmed=True)
        self.channel = accepted["channel_id"]

    def test_cross_author_request_id_collision_fails_closed(self):
        from src.persistence.errors import PersistenceConflictError
        bob_msg = self.product.send_message(
            self.bob.access_token, self.channel, "hello",
            request_id="msg-1", confirmed=True)
        with self.assertRaises(PersistenceConflictError):
            self.product.send_message(
                self.alice.access_token, self.channel, "hello",
                request_id="msg-1", confirmed=True)
        thread = self.product.read_messages(self.alice.access_token,
                                            self.channel)["messages"]
        self.assertEqual([m["message_id"] for m in thread], [bob_msg["message_id"]])
        self.assertEqual([m["author"] for m in thread], ["counterpart"],
                         "Alice must not see a message attributed to herself "
                         "that she never sent")

    def test_same_author_replay_is_still_idempotent(self):
        first = self.product.send_message(
            self.bob.access_token, self.channel, "same text",
            request_id="msg-2", confirmed=True)
        replay = self.product.send_message(
            self.bob.access_token, self.channel, "same text",
            request_id="msg-2", confirmed=True)
        self.assertEqual(first["message_id"], replay["message_id"])
        thread = self.product.read_messages(self.bob.access_token,
                                            self.channel)["messages"]
        self.assertEqual(len(thread), 1, f"replay must not duplicate: {thread}")


class RotationDoesNotStrandAnotherClient(unittest.TestCase):
    def test_rotation_revokes_the_previous_token_and_issues_a_usable_one(self):
        live, identity, product, alice, a_session, bob, b_session = two_user_world()
        rotated = product.rotate_session(alice.access_token)
        self.assertNotEqual(rotated.access_token, alice.access_token)
        self.assertNotEqual(rotated.csrf_token, alice.csrf_token)
        from src.identity.models import AuthenticationError
        with self.assertRaises(AuthenticationError):
            product.list_requests(alice.access_token)
        self.assertEqual(product.list_requests(rotated.access_token),
                         {"incoming": [], "outgoing": []})


if __name__ == "__main__":
    unittest.main()
```

## Appendix E — live-page probes

`live_page_probe.py` (live server) and `main_page_probe.py` (accepted `main`)
both: start the product server, open `/` in headless Chromium, and record failed
requests, console messages, `window.RESONANCE_MODE`, `.match-card` count and the
first lines of visible text. The `main` variant deliberately touches only
pre-R14 surfaces so its result is attributable to R13/R13B.

Observed on `3397e96`:

```json
{"failed_requests": ["404 /api/config", "404 /api/context",
                     "401 /api/product/rotate", "403 /api/webmcp/discover?source=live"],
 "match_cards": 0, "match_cards_after_discover": 0,
 "request_buttons_after_discover": 0,
 "visible_headline": ["Resonance", "VISUAL DISCOVERY · R9", "Checking consent",
                      "Collab · WebMCP unavailable", "ACTIVE THOUGHT",
                      "Loading accepted context…", "Preparing the shared Thought DNA."]}
```

Observed on accepted `main` @ `d2f0d24`:

```json
{"failed_requests": ["404 /api/config", "404 /api/context"],
 "csp_blocked_inline": true, "resonance_mode_set": null, "match_cards": 0,
 "visible_text": ["Resonance", "VISUAL DISCOVERY · R9", "Checking consent",
                  "ACTIVE THOUGHT", "Loading accepted context…",
                  "Preparing the shared Thought DNA."]}
```

The `main` run is the attribution evidence: identical failure with no R14 code
present.

---

# Addendum 3 — post-acceptance verification, and two corrections to Addendum 2

R14 was ACCEPTED and merged while this run was in flight: PR #116 at exact head
`2d4387e`, landing on `main` as `47b6d58`. Addendum 2 was written against
`3397e96` and two of its claims do not survive the merged head. Recording the
corrections here rather than leaving the artifact's earlier text to stand.

## Correction 1 — B1a is closed, and by a better fix than I proposed

Addendum 2 said the "Request intro" control "cannot render anywhere, on any
head, with or without my patch", because it attached to `.match-card` elements
that the live origin never renders. That was accurate for `3397e96`. It is
**wrong for the merged head**.

The author did not patch the guard. They added a **`Start an introduction`
panel section** that runs its own `/api/product/rich_discover` and renders a
button per intro-accepting candidate, independent of the R9 replay cards, and
sets `document.body.dataset.querySession`. That sidesteps the dead R9 page
entirely — a better fix than my candidate patch, which only bypassed the guard
on cards that were never going to exist.

Verified on `47b6d58` by real clicks in headless Chromium, two browser contexts
(two cookie jars), the whole of #86's scenario through the **human UI**:

| step | observed |
| --- | --- |
| B's initiation surface | `Start an introduction / guest-9be30b / Request intro` — 1 button (was 0) |
| B clicks **Request intro** | Outgoing → `requested: <message>` + **Cancel** |
| A reloads | Incoming → `guest-2276af / requested: <message>` + **Accept** / **Decline** |
| A clicks **Accept** | buttons become **Open channel** |
| A opens channel, types, clicks **Send** | sent |
| B reloads, opens channel | `guest-9be30b: throttle input power at the bloom edge` |
| contact data in the panel | none — pseudonyms only |

## Correction 2 — the CSP finding was overstated

Addendum 2 and my first #88 comment presented the CSP refusal of the injected
`window.RESONANCE_MODE` script as part of a release blocker. It is real, but
**functionally harmless**: that flag is written by the inline script and **read
nowhere** in the repository — no `.mjs`, `.html` or `.py` consumes it. Worth
cleaning up (a strict-CSP page should not ship a script the browser always
refuses) but not a blocker, and I should not have listed it beside the real
cause. Only the unrouted endpoints matter.

## The R13 live-page defect, scoped properly

Still open on `47b6d58`. The live server routes none of `/api/config`,
`/api/context`, `/api/discover?source=…`, all three of which `app.mjs` needs;
`boot()` throws on the first two, so the R9 visual view never initializes and
the page sits on its loading placeholders.

It is **not** a routing shim, which is why Addendum 2's promise of a patch is
not fulfilled here. The page hard-asserts a fixture-shaped contract —
`resonance-ui-context/0.1` with `pinned_request.mode === "analogical"` and
`k === 15`, and `public_context()` builds its active thought from the **R7
flagship fixture session**. Serving those routes from the live server means
either handing a judge a fixture-backed map, contradicting the canonical data
rule this milestone exists to establish, or building a live per-viewer context
and discovery mapping that still satisfies the pinned assertions. The second is
genuine R13 integration work and not something to drop into a release path
unverified hours before a freeze. Three options with a recommendation are on
#88; I offered to implement and browser-verify whichever the maintainer picks,
and will not touch accepted surfaces without that go-ahead.

What does work on the live origin, verified: every product API, and R14's
collaboration panel end to end — precisely because it builds its own surface
from `rich_discover` instead of depending on the R9 page. What is dark is
specifically the R9 map / match cards / evidence drawer.

## The other two items at the merged head

- **026B-N2 — closed, stronger than I proposed.** I suggested binding the author
  into the request *hash*, which only converts the collision into a visible
  conflict. The author namespaced the `request_id` itself per subject, so Alice
  reusing Bob's `msg-1` stores a **distinct** message: `got_bobs_id: false`,
  thread `[('counterpart','hello'), ('me','hello')]`, both persisted, and
  same-author replay still idempotent. That solves the global-keyspace problem I
  had written off as R11-level.
- **F4 — closed.** The token is shared across tabs via `localStorage`, so a
  second tab reuses it instead of rotating, and a rejected proof re-bootstraps
  once. Second tab's token no longer differs; tab 1's write after tab 2 opens
  returns `OK` where it previously failed `csrf_rejected` twice.

## Standing of this run

Every finding this run produced — F1 (independently matching 026B's N1), F2, F4,
B1a, and the executed confirmations of B1/B2/B3 — was accepted by the canonical
author and closed with a regression. Two were closed by better fixes than the
patches I offered, which is the right outcome: the reviewer's job was to prove
the defect and hand over something runnable, and the author's job was to choose
the design. F3 (PostgreSQL migration loader) and the R13 page defect remain open
on #88 as `main`-level items, neither charged to R14.

Corrections above supersede Addendum 2 where they conflict. The `3397e96`
evidence stands as a record of that head, not of the merged product.
