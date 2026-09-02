---
mission: R11-PERSISTENCE
run: R11-PERSISTENCE-REVIEW-M4P9
review_type: additional exact-head review / reproduction
contributor: Parshkov
agent_id: parshkov-openai-gpt56sol-r11review-m4p9
agent_or_model: OpenAI GPT-5.6 Sol
provider: OpenAI
date: 2026-09-02
mission_modified: false
web_research_used: false
code_execution_used: true
blind_constraints_preserved: not-applicable
reviewed_pr: https://github.com/Parshkov/Resonance/pull/108
exact_head: 67514cfd91ad8df66a84b97dee169c578d809265
base_main: dd93f349808ec2006b902e226edf2fe2eb95763d
verdict: REVISION_REQUESTED
conflict_of_interest: >
  Fresh review run and not an author of PR #108 or superseded PR #95, but the
  recovery author is also an OpenAI GPT-5.6 Sol run. This is useful additional
  exact-head review input and does not claim to satisfy the maintainer's
  preference for a different-provider final acceptance review.
execution_limit: >
  The sandbox could not resolve github.com, so a clean checkout, full repository
  suite, git diff --check, and live PostgreSQL smoke could not be executed here.
  Exact head files/diff were inspected through the connected GitHub tool.
  Two SQLite durability/concurrency findings were reproduced with standalone
  Python 3 stdlib scripts matching the submitted SQL/order of operations.
---

# Scope

Review canonical R11 recovery PR #108 at exact head
`67514cfd91ad8df66a84b97dee169c578d809265` against issue #83, including the
`REOPEN_CANONICAL` recovery gates and the earlier durability/retry addendum.

The review focused on the load-bearing R11 properties:

- durable DB/index generation and fail-closed visibility;
- crash-safe versioned migrations;
- immutable ownership and monotonic revocation;
- retry/idempotency semantics for state-changing service operations;
- optimistic session versions;
- deterministic rebuild and metadata/ranking separation;
- SQLite/PostgreSQL repository parity where static inspection permits.

This is review input, not maintainer `REVIEW_STATUS`, and it does not occupy or
reopen the R11 canonical slot.

# Inputs reviewed

- issue #83 complete mission/recovery contract and retry-safety addendum;
- PR #108 exact metadata, comments, full changed-file list and exact-head files;
- `ops/migrations/0001_init.sql` and `0002_recovery_generation.sql`;
- `src/persistence/service.py`, `sqlite_store.py`, `postgres_store.py`,
  `repository.py`, `models.py`, `sql.py`, `seed.py`;
- `tests/test_persistence.py` and `tests/test_persistence_recovery.py`;
- accepted R7/R8 consent/discovery adapters used by the R11 rebuild boundary.

# Method and measured evidence

A network clone was attempted and failed with:

```text
fatal: unable to access 'https://github.com/Parshkov/Resonance.git/':
Could not resolve host: github.com
```

Therefore this run does **not** inherit or claim the author's unexecuted test
commands. The exact head was reviewed through GitHub file/diff reads.

Two focused SQLite reproductions were executed locally with Python stdlib.
They reproduce the submitted ordering/SQL, not a hypothetical alternative.

## Reproduction A — migration checkpoint crash

`SQLiteRepository.migrate()` executes a migration with `executescript(sql)` and
only afterwards records its version in `schema_migrations`. The connection uses
`isolation_level=None`. Recovery migration `0002_recovery_generation.sql`
contains the non-idempotent statement:

```sql
ALTER TABLE sessions ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
```

Simulating process loss after `executescript(0002)` but before the separate
migration-marker insert produced:

```text
have markers: {'0001_init'}
version column present: True
rerun: OperationalError: duplicate column name: version
```

The database is therefore schema-ahead-of-marker and normal startup cannot
complete the migration on retry.

## Reproduction B — committed revocation overwritten by stale profile upsert

The service profile path reads the existing `UserRecord`, preserves the
`revoked_at` value it saw, then `put_user()` performs an unconditional upsert:

```sql
... ON CONFLICT(user_id) DO UPDATE SET
... revoked_at=excluded.revoked_at
```

Using two SQLite connections to model two service processes:

1. process A reads a live user (`revoked_at = NULL`);
2. process B commits revocation;
3. process A performs the submitted upsert using its stale object.

Measured result:

```text
revocation after B commit: revoked
after stale profile upsert: ('A2', None)
```

The committed revocation was removed.

# Blocking findings

## F1 — P1: SQLite migrations are not crash-atomic and can brick restart

**Files:** `src/persistence/sqlite_store.py`,
`ops/migrations/0002_recovery_generation.sql`

The recovery mission explicitly requires versioned migrations and restart-safe
durability. In the submitted SQLite path, schema mutation and migration marker
are separate autocommit checkpoints. A crash at the demonstrated boundary
leaves `version` installed while `0002_recovery_generation` is absent from
`schema_migrations`; the next startup reruns `ALTER TABLE ... ADD COLUMN` and
fails permanently until manual repair.

This is not covered by `test_old_0001_database_upgrades_without_rewriting_history`,
which tests only the no-crash happy path.

**Required revision:** make each migration plus its marker one recoverable
atomic unit, or make every migration explicitly restart/idempotency safe and
repair schema-ahead-of-marker state. Add a failure-injection/restart test at the
boundary between schema application and marker persistence.

## F2 — P1 privacy/durability: normal user upsert can resurrect a committed revoke

**Files:** `src/persistence/service.py`, `src/persistence/sqlite_store.py`,
`src/persistence/postgres_store.py`

`LiveCorpusService.create_user()` tries to preserve revocation, but that check is
a read-before-write protected only by the service instance's in-process lock.
The repository upsert then blindly assigns `revoked_at=excluded.revoked_at`.
A second process can commit a revoke after the first process's read; the stale
profile upsert then clears it. The same logical race exists on PostgreSQL because
`put_user()` has no row-version/precondition/monotonic-revocation guard.

This is especially dangerous because `revoke_user()` commits the user revoke and
then revokes sessions in separate repository transactions. The user-level hidden
flag is what keeps any not-yet-processed session fail-closed if the process dies
mid-loop. A later stale profile upsert can remove that guard.

The submitted concurrency smoke uses one `LiveCorpusService` instance, whose
`RLock` serializes its threads, so it cannot detect this cross-instance/process
race.

**Required revision:** make normal user revocation monotonic at the repository
transaction boundary (for example user optimistic versioning / locked current
row + explicit transition rules, or an upsert that cannot clear an existing
revoke). Any administrative un-revoke/restore must be a separately named
privileged path. Add a two-repository/process-equivalent regression where a
stale profile update races a committed revoke and the revoke wins.

## F3 — P1/P2 acceptance gap: user state-changing operations do not satisfy the declared retry contract

**File:** `src/persistence/service.py`

Issue #83's durability addendum requires state-changing service methods to
support stable idempotency/request keys (or equivalent deterministic
idempotency) so agent/WebMCP/remote-MCP retries do not duplicate audit/state.
Session methods implement this, but user methods do not:

- `create_user()` has no `request_id`; repeating the same logical create/upsert
  writes a new `updated_at`, appends another audit event, bumps corpus generation,
  and rebuilds again;
- `revoke_user()` has no durable request key. If its DB mutation commits but
  `rebuild_index()` then fails, a retry sees `revoked_at` already set and returns
  early without healing the stale serving generation.

The current timeout/retry tests exercise session revoke, not the user paths.

**Required revision:** extend the durable idempotency/version contract to user
mutations that R12/R12B will call, and add retry-after-ambiguous-commit tests.
At minimum, retrying the same logical user create/update must not duplicate the
audit event/generation, and retrying a committed user revoke after rebuild
failure must restore a current serving generation (or explicitly force rebuild)
without reapplying the mutation.

# Positive findings

The review did not find a new matching/ranking implementation in persistence.
The submitted rebuild indexes only Thought DNA into a fresh accepted engine and
joins consented metadata through the accepted discovery registry afterwards.

The session path also materially improves the superseded R11 foundation:

- DB `corpus_generation` vs `serving_generation` is checked before discovery;
- session ownership is checked inside repository transactions;
- session optimistic versions reject stale writes;
- session request-id replay/collision state is committed with mutation/audit;
- committed session visibility reductions leave the service stale/fail-closed if
  rebuild fails;
- deterministic rebuild checks DB generation before publication.

Those improvements are real, but they do not remove F1-F3.

# Validation still required after revision

A clone-capable, preferably different-provider reviewer should execute on the
new exact head:

```bash
python3 -m compileall -q src tests demo
python3 -m unittest tests.test_persistence -v
python3 -m unittest tests.test_persistence_recovery -v
python3 -m unittest discover -s tests -v
git diff --check <accepted-base>..<new-head>
```

and, with an isolated database:

```bash
RESONANCE_TEST_POSTGRES_URL=postgresql://... \
  python3 -m unittest tests.test_persistence -v
```

Additional required regression probes from this review:

1. interrupted SQLite `0002` application restarts successfully;
2. two repository/service instances race profile upsert vs revoke; revoke cannot
   be cleared by an ordinary write;
3. repeated user create/update with one request key produces one committed audit
   outcome;
4. user revoke commit followed by injected rebuild failure is safely healable by
   retry/restart without duplicate mutation.

# Verdict

**REVISION_REQUESTED on exact head
`67514cfd91ad8df66a84b97dee169c578d809265`.**

F1 is a demonstrated restart/durability failure in the required SQLite judge
path. F2 is a demonstrated cross-process revocation rollback that can violate the
privacy boundary. F3 is a direct gap against issue #83's acceptance-critical
retry/idempotency contract. Do not mark R11 accepted until these are fixed and a
new exact head receives independent execution/review.
