# R12C Session Ingestion

This package implements the **private preparation boundary** between a normal
agent/user conversation and the accepted Thought DNA contract.

It intentionally does **not** own users, durable persistence, consent policy, or
matching. Those remain R11/R12/R12B/R13 responsibilities.

## Contract

Two inputs are supported:

1. `prepare_structured(...)` — preferred. A host agent supplies valid
   `thought-dna/0.1`.
2. `prepare_raw_text(...)` — fallback. Uses the accepted deterministic
   `CueExtractor`; implicit structure stays an abstention rather than being
   invented.

Both produce only `prepared_private` state. A caller must then:

1. call `preview(draft_id)`;
2. show the exact graph/display/location intent to the human;
3. receive explicit approval;
4. call `share_prepared(...)` with the opaque confirmation token and an
   authenticated subject.

The core `share_prepared` method calls an injected `ShareSink`; it never owns a
database or index. `IdentityIngestionService` is the product adapter. It stores
the sanitized graph immediately as a private R11 session through R12
`IdentityService`, records only non-source draft metadata in durable events,
and flips consent through the same R12B-authorized mutation after confirmation.
The core draft is consumed only after the durable sink returns successfully.

## Data minimization

Raw source text is never assigned to service state. Prepared Thought DNA is
sanitized before storage in the ephemeral draft store:

- `source.text` is replaced with an empty string and the matching empty SHA-256;
- node/relation spans and lexical cue spans are removed;
- structural labels/roles/relations, uncertainty/assertion/modality and
  Knowledge DNA annotations remain.

The durable share handoff records the ingestion kind, extractor version for the
fallback path, warnings/abstentions, and `source_retained=false`; it does not
forward the original source text or raw source hash.

The server-generated draft ID and authenticated `subject` are separate from
agent-supplied Thought DNA. Product ownership/session/consent control fields in
the candidate are rejected.

Prepared private drafts retain the sanitized structured graph until the owner
shares, explicitly discards, or deletes the account. Discard tombstones the
private session; ordinary audit/backup retention may retain that tombstone but
never the raw source excerpt. This is the pilot draft-retention policy.

## Limits

Default foundation limits:

- 64 KiB structured candidate;
- 20,000 characters raw fallback context;
- 64 nodes;
- 128 relations;
- 8 KiB presentation/location metadata.

Final hosted limits may be tightened by R12B, but transports must not bypass
this boundary.

## Product adapters and tool actions

`ManualIngestionAdapter`, `WebMCPIngestionAdapter`, and
`RemoteMCPIngestionAdapter` expose the same owner-scoped service. Their canonical
tool-shaped actions are:

- `resonance_prepare_thought`
- `resonance_get_share_preview`
- `resonance_share_prepared_thought`
- `resonance_discard_prepared_thought`

Browser adapters carry exact-origin and CSRF proof. Remote MCP carries the
bound protocol-session ID. Agent-facing preparation/preview results include
`untrustedContentHint` metadata because labels originate in user content.

Durable confirmation tokens require a stable deployment secret. Construct
`IdentityIngestionService` with either an explicitly configured core or
`confirmation_secret`; it refuses to invent a process-local secret that would
invalidate every preview after restart.

The R11 consent write uses the original prepared version plus a durable request
ID. A response-lost retry replays the same commit, while unrelated mutation of
the private row makes the old preview fail closed. R11's generation barrier
keeps discovery unavailable if an index rebuild cannot prove freshness.

R11/R12/R12B are still pending exact-head review at the time of this integration.
Their current heads are merged here for executable evidence; R12C acceptance
must not be recorded until those prerequisites are explicitly accepted.
