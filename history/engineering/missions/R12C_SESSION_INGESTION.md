# R12C-SESSION-INGESTION — submission record

## Coordination and provenance

- canonical issue: #92
- canonical run: `R12C-SESSION-INGESTION`
- original claimant/author: `parshkov-openai-gpt56sol-chat-i92c`
- original claim: issue comment `5504195127`
- recovery/integration agent: `parshkov-openai-gpt5-codex-u4m8`
- human sponsor: Parshkov
- recovery authority: `work/CODEX_CONTINUOUS_EXECUTION.md`
- blind constraints: none

The original run produced PR #102 and the private in-memory foundation but did
not post `SUBMIT`. The maintainer continuous-execution directive explicitly
assigns completion of that existing PR. This recovery did not create a duplicate
canonical claim; it continued the existing branch and preserves the original
foundation commits.

## Integrated dependency heads

- R11 persistence recovery: `5f06cad075d118280b11faa7c20afcad3a875510`
- R12 identity/consent recovery: `5cb06b96acb08aa16d562dd1ece4816a7a3800fe`
- R12B security integration: `91f3ad6a6830df48d5200e279def5f9322d60c7f`

These are current submitted heads, not self-declared accepted prerequisites.
R12C remains pending review/blocking resolution until their canonical issue
streams explicitly record acceptance.

## Delivered behavior

1. Structured and deterministic raw-text preparation use the accepted graph and
   extractor contracts with strict input/graph/metadata bounds.
2. Raw source text, spans, and cues are removed before durable storage. Extracted
   graphs become schema-valid sanitized manual artifacts; original extractor
   identity and warnings remain in ingestion provenance.
3. Durable preparation writes a private R11 session through the authenticated,
   R12B-authorized R12 service. Caller ownership and consent fields are rejected.
4. Preview and discard are owner-scoped and recover across restart. Discarded
   artifacts are tombstoned and never enter discovery.
5. Share requires an exact HMAC preview token plus explicit confirmation. A
   stable deployment secret is mandatory for restart-safe tokens.
6. Consent/index publication uses the original prepared optimistic version and a
   durable request ID. Ambiguous post-commit retries replay; unrelated changes
   reject the stale preview.
7. Manual UI, browser WebMCP, and remote MCP adapters expose the same four
   canonical tool actions and identical persisted Thought DNA.
8. Browser paths require exact-origin CSRF proof; remote paths can carry the
   R12B subject/client-bound protocol session.
9. Agent-facing preparation/preview results are marked as untrusted content.

## Retention truth

Sanitized private drafts are retained until share, explicit discard, or account
deletion. Discard creates a durable deletion tombstone subject to the documented
pilot audit/backup retention. Raw excerpts and reconstructable spans/cues are not
stored; diagnostic strings persisted for restart are redacted where the accepted
extractor may quote a source fragment.

## Validation

Executed on the final recovery tree:

```text
python3 -m unittest tests.test_session_ingestion tests.test_ingestion_identity_integration -v
```

Result: **20 tests / 20 OK**.

```text
python3 -m unittest discover -s tests
```

Result: **274 total / 272 passed / 2 skipped**. The skips require an isolated
`RESONANCE_TEST_POSTGRES_URL`; no live PostgreSQL result is claimed.

`python3 -m compileall -q src tests` and `git diff --check` also completed cleanly.
