# R14B-WORKSPACES — run record

> **Superseded in part (2026-09-06).** This mission was written when the
> product had two persistence backends. Resonance now runs on **PostgreSQL
> only** — `src/persistence/sqlite_store.py` is deleted and there is no
> SQLite path to build, mirror or keep at parity. The rest of the contract
> stands; this file is kept as the record of what was asked at the time.

- mission: #91
- canonical agent: `dima2010-anthropic-fable5-7328` (Anthropic / Claude Fable 5)
- run_id: `R14B-WORKSPACES-F5`
- base: accepted main `457506be` (R14 merged)

## Model

`0004_workspaces.sql` adds `workspaces`, `workspace_members`, `workspace_notes`,
`workspace_tasks`, `workspace_artifacts`, `workspace_links`, `workspace_activity`
(SQLite + PostgreSQL parity). `src/workspaces/` composes over the accepted
layers:

- **Bootstrap seam** — a workspace is created ONLY from an accepted R14
  `intro_id` the caller participates in (both parties unblocked); membership is
  derived from that intro's two subjects, never a client-supplied id.
- **Membership state machine** — the creator is `owner`/`active`; the peer is
  `member`/`invited` and sees **no** workspace-private content until they
  explicitly accept. Roles: `owner` (admin), `member` (write), `viewer` (read).
  Any write member may invite an already-connected, unblocked user; owner may
  remove; a member may leave; owner may not leave. 2+ members from day one.
- **Current-state authorization** — every membership and content op re-checks
  the caller's current membership+role at write/read time, so a removed or
  departed member loses access immediately (membership changes move no global
  counter — the R13B/get_match discipline). Non-members get one uniform
  "unavailable" error for foreign, missing, and not-a-member references (opaque
  ids, enumeration-resistant).
- **Shared work** — idea brief (optimistic `version`), notes, lightweight tasks
  (`todo/doing/done`), a linked Resonance match with a consent-safe `why`,
  artifact **metadata only** (label/kind/sha256/size — no raw contact-bearing
  filenames, content stored out of band), and an activity timeline.
- **UGC discipline** — all member/note/task/link text returns `untrusted: true`
  and is never interpreted; audit carries ids only.
- **Generation invariant** — no workspace write touches the corpus generation.

## Surfaces

- HTTP: `/api/product/workspaces`, `/api/product/workspace` (read);
  `/api/product/workspace/{create,invite,respond,remove,leave,brief,note,task,task_state,link,artifact}`.
- WebMCP: additive `demo/ui/workspaces.mjs` — `resonance_create_workspace`,
  `resonance_list_workspaces`, `resonance_get_workspace`,
  `resonance_respond_workspace_invite`, `resonance_add_workspace_note`,
  `resonance_add_workspace_task` — `readOnlyHint` on reads,
  `untrustedContentHint` on any returned text, `confirm` on writes.

## Evidence

`tests.test_workspaces` (8): bootstrap requires an accepted intro + participant;
invitee sees nothing until accept; 2+ member shared work (notes/tasks/brief/
link/artifact/activity); invite requires connection + write role; removed member
loses access immediately with no generation move; owner-cannot-leave/member-can;
uniform enumeration-resistant negatives; no workspace write bumps the corpus
generation. `tests.test_product_http` workspace flow over real HTTP. Migration
0004 applies atomically; the accepted R11 migration-list assertions are extended.

```
python3 -m unittest tests.test_workspaces -v
python3 -m unittest tests.test_product_http
python3 -m unittest discover -s tests
```
