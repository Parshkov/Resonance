# R12B security policy runtime

`src/security` is the transport-neutral security/data-governance kernel for the hosted Resonance pilot. It is intentionally separate from storage, identity, discovery, WebMCP, and remote-MCP transports: those surfaces must call this policy layer rather than copy authorization rules.

## Contract

Version: `resonance-security/0.1`

The runtime enforces these invariants:

- **private by default**: unknown actions fail closed;
- **authoritative server-side ownership**: callers provide only opaque resource kind/id; owner, workspace, consent, block, and peer capabilities are resolved from `PolicySource`;
- **no token-scope privilege inflation**: token claims may narrow a current server-side grant, never widen it;
- **grant drift protection**: MCP/long-lived protocol sessions are bound to subject + client and carry a policy-generation checkpoint; every protected call is re-evaluated against current authoritative state before an old checkpoint advances;
- **immediate revocation effects**: revoked discovery sessions, removed workspace members, and blocked peers are denied on the next call;
- **auditable sensitive writes**: share/revoke/delete/intro/message/invite/member-removal/block operations require confirmation where applicable and generate content-minimized decision records;
- **OAuth subject binding**: authorization-code issuance accepts an authenticated `RequestContext`, never a caller-supplied username, and binds code to subject/client/redirect/PKCE/resource/audience;
- **untrusted UGC boundary**: other-user text is escaped for rendering and carries `untrustedContentHint` metadata for agent integrations;
- **abuse/privacy guards**: deterministic rate limits, request/graph/depth limits, coarse-location validation, small-bucket suppression, CSRF/origin checks, HTTPS/restrictive-origin policy, and URL-secret rejection.

## Integration seam

Production code supplies a `PolicySource` adapter backed by accepted product state. The adapter must resolve current policy generation, resource owner, containing workspace, per-session consent/revocation, workspace membership/role, collaboration/peer capability, block state, and current auth-session validity.

The included `InMemoryPolicySource` is a deterministic test/pilot adapter only. It is **not** intended to become a second product database.

`src.identity.security.IdentityPolicySource` is the current R11/R12 adapter. It resolves ownership and consent from corpus rows and resolves authentication, intro consent, blocks, reports, and minimized policy-decision events from the R11 audit-event store. It creates no second policy database. `IdentityService` constructs this adapter and requires `SecurityPolicy.authorize()` for owner views, Thought creation/update/share/revoke/delete, discovery projection, account export/deletion, and block/report operations.

R14 remains responsible for extending this adapter with authoritative workspace membership and artifact/message relationships. Unknown workspace state continues to fail closed. R15 must use `IdentityService.request_context()` plus `bind_protocol_session()` and pass the bound ID on each protected call.

### R12 identity/consent handoff

Authentication creates `RequestContext(subject, client_id, auth_session_id, actor_type, token_scopes)`. The security layer never accepts a user/owner override in `ResourceRef`.

Cookie-authenticated mutations use `CsrfGuard` with a session-bound CSRF digest and an exact configured origin. `ManualUIAdapter` and `WebMCPAdapter` require a request origin at construction and delegate to the same policy-backed service.

### R15 remote MCP handoff

On MCP initialize, call `SessionGrantRegistry.bind()` after authentication. On every subsequent protected tool call, pass the same authenticated context and `Mcp-Session-Id` to `SecurityPolicy.authorize()`.

A protocol session belonging to another subject/client is rejected even when the session ID itself is valid. Policy-generation changes are re-evaluated from authoritative state before a checkpoint can advance.

OAuth authorization lives in `src/remote/oauth.py` (`OAuthCore`, PKCE S256, audience-bound access tokens); the earlier `AuthorizationCodeBroker` duplicate in this package was removed on 2026-09-04. Authorization codes are issued only for a server-authenticated subject; there is intentionally no `user` or `username` parameter.

## Deployment controls that remain deployment evidence

This module cannot prove managed-database encryption, encrypted/access-controlled backups, private object storage, TLS termination, production CSP/CORS headers, real backup retention, or deployed log routing. Those controls remain required by `SECURITY.md`, `docs/THREAT_MODEL.md`, and #89 and must be verified on the exact hosted release candidate.

The current combined R11/R12 integration suite proves durable product-path enforcement, restart-safe block/revoke behavior, protocol-session binding, minimized decision logs, and policy-preserving backup/restore. Production TLS, managed-storage, retention, and hosted-log evidence remains a release-freeze requirement rather than something unit tests can establish.
