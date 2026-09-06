# Resonance Pilot Threat Model

This threat model covers the planned hosted multi-user Resonance product: browser UI + WebMCP, product API, durable PostgreSQL persistence, remote MCP, structural discovery, introductions/messages, and multi-person workspaces.

## Assets to protect

- owner-private Thought DNA drafts and unshared sessions;
- authentication/session credentials;
- consent choices and revocation state;
- private messages and collaboration workspaces;
- private artifacts/media;
- non-public profile/contact information;
- consented coarse location against re-identification or inference;
- integrity of structural match order, scores, evidence, and provenance;
- audit records and deployment secrets.

## Trust boundaries

1. **Browser / WebMCP client -> product service**
   - browser-provided IDs and actor claims are untrusted;
   - authorization must resolve authenticated subject server-side.

2. **Remote MCP client -> product service**
   - tokens/authorization define subject scope;
   - tool arguments cannot override owner/membership/consent decisions.

3. **Other-user content -> current user's browser/agent**
   - all labels/messages/notes/artifacts are untrusted UGC;
   - prompt injection and XSS must fail safely.

4. **Product service -> structural engine/index**
   - only validated, consented Thought DNA may enter discoverable state;
   - metadata/location may not influence semantic ranking.

5. **Product service -> database/object storage/logging**
   - storage credentials stay outside source;
   - private media and records remain access-controlled;
   - logs are minimized.

## Threats and required mitigations

### IDOR / cross-user object guessing

**Threat:** user or agent substitutes another session/workspace/message ID.

**Required:** every read/write performs subject + ownership/membership authorization; random/opaque IDs are defense-in-depth only.

**Test:** user B cannot read, mutate, delete, share, or attach to user A's private object by ID substitution.

### Unauthorized sharing / consent mutation

**Threat:** an agent prepares a thought and silently publishes it, or changes consent for another session.

**Required:** `prepare` and `share` are distinct; state-changing sharing/revocation requires authenticated ownership and visible confirmation path; no indexing before committed share state.

**Test:** preparation/discard leaves no discoverable artifact; spoofed owner/consent fields are ignored/rejected.

### Revocation and stale-index leakage

**Threat:** revoked/deleted session remains searchable or still contributes to map/aggregates.

**Required:** revocation atomically updates durable state and live discoverability; rebuild is deterministic and excludes revoked records.

**Test:** candidate disappears from structured result, rich visual, heatmap bucket, and rebuilt index after revoke/restart.

### Prompt injection through UGC

**Threat:** a matched profile/message/note contains instructions intended to control the receiving agent.

**Required:** UGC is marked/handled as untrusted data; static tool schemas/descriptions; no UGC is executed or promoted to trusted instructions.

**Test:** malicious text is returned/rendered as content and cannot alter authorization/tool definitions or silently trigger writes.

### XSS/content injection

**Threat:** display names/messages/artifacts execute browser code.

**Required:** escaped rendering; no arbitrary executable HTML/SVG uploads; MIME/type/size allowlists for media.

**Test:** standard script/event-handler payloads render inert.

### CSRF / session fixation

**Threat:** attacker causes authenticated browser mutation or reuses fixed session identity.

**Required:** SameSite/Secure/HttpOnly cookies as applicable, CSRF defense for cookie-authenticated writes, session rotation on login/privilege changes, logout invalidation.

**Test:** cross-origin mutation fails and old session identity is invalidated after rotation/logout.

### Location inference

**Threat:** coarse pins or tiny aggregate buckets reveal a hidden individual's location.

**Required:** exact GPS/address not required; only consented coarse location; small-bucket suppression (default target >=3) or documented equivalent; hidden/revoked users excluded.

**Test:** bucket below threshold is not rendered/returned and hidden sessions cannot be inferred by before/after counts.

### Private media leakage

**Threat:** artifact URL can be shared with an unauthorized user or reused after membership removal.

**Required:** private object storage and authenticated/proxied or short-lived signed access; membership checked at issue time; cache private/user scoped.

**Test:** user outside workspace and removed former member cannot fetch private artifact.

### Abuse / denial of service

**Threat:** oversized Thought DNA, graph explosion, discovery spam, invite/message spam.

**Required:** JSON/schema validation, graph node/edge/depth bounds, request-size limits, rate limits, bounded work queues/timeouts, block/report.

**Test:** oversized/adversarial payload is rejected before expensive matching; deterministic rate-limit behavior is observable.

### Secret/private-data leakage in logs

**Threat:** tokens, raw Thought DNA, messages, or contact information are copied into logs/traces.

**Required:** explicit logging allowlist/minimization; redact auth headers/tokens; use correlation IDs.

**Test:** representative auth/share/discover/message flows produce logs free of prohibited payloads.

### Ranking manipulation through metadata

**Threat:** location/profile/display metadata changes structural match rank or score.

**Required:** accepted structural engine remains authoritative; metadata joins after matching and only for authorized presentation.

**Test:** metadata permutation leaves match IDs/order/scores/evidence unchanged.

### Workspace privilege escalation

**Threat:** non-member or removed member reads/writes workspace state; agent impersonates another member.

**Required:** membership/role check on every operation; actor identity taken from authenticated subject; audit actor type + subject.

**Test:** invitee cannot read before acceptance; removed member loses future access immediately; agent cannot set arbitrary actor identity.

## Security acceptance evidence

Before hosted pilot release, preserve evidence for:

- automated cross-user authorization tests;
- share/preview/revoke/restart tests;
- XSS/prompt-injection handling;
- CSRF/session tests;
- rate and payload-size tests;
- heatmap small-bucket tests;
- private media authorization tests if media ships;
- representative sanitized-log inspection;
- backup/restore test preserving access controls;
- independent security-focused review of the exact release candidate.

A green functional suite alone is not a security acceptance signal.
