# R15 Remote MCP — independent exact-head review of PR #93

## Review identity and provenance

- `base_mission`: `R15-REMOTE-MCP`
- `review_run_id`: `R15-REMOTE-MCP-REVIEW-S9K4`
- `agent_id`: `parshkov-openai-gpt56sol-r15review-s9k4`
- `human_sponsor`: `Parshkov`
- `provider`: OpenAI
- `model`: GPT-5.6 Sol
- `execution_environment`: ChatGPT connected session with GitHub connector; local analysis sandbox without a network GitHub checkout
- `reviewed_pull_request`: https://github.com/Parshkov/Resonance/pull/93
- `reviewed_exact_head`: `4a136ff0a7a1bb59d08adf772c380c5a5cb1f77d`
- `canonical_author`: `dima2010-anthropic-fable5-7328` / Anthropic Claude Fable 5
- `independence`: different provider and run identity from the canonical author; no blind group applies
- `mission_modified`: no

## Review method and evidence boundary

I inspected the complete PR metadata and every changed source/test surface at exact head `4a136ff0a7a1bb59d08adf772c380c5a5cb1f77d`, the accepted engine/discovery seams on current `main`, issue #87 and its review history, the current #89 security addenda, and the MCP specification that the implementation itself advertises: protocol version `2025-03-26`.

Official protocol references used for conformance checks:

- https://modelcontextprotocol.io/specification/2025-03-26/basic/transports
- https://modelcontextprotocol.io/specification/2025-03-26/basic/authorization

This runtime cannot obtain a network clone of GitHub, so I **did not independently rerun** the author's claimed `170 tests OK` result or execute a generic MCP Inspector/OpenAI/Anthropic client. Those author results remain provenance from PR #93, not results of this review. Static protocol failures below are directly reproducible from the exact source and should receive executable regression tests in the next revision.

## Verdict

**REQUEST_CHANGES / NOT R15-ACCEPTANCE-READY.**

PR #93 is useful as a remote transport/rich-result foundation. I agree with the existing maintainer assessment that it should remain open and should not be merged or recorded as completed R15 yet. The core transport/service separation and complete structured discovery payload are worth preserving.

There are two distinct classes of remaining work:

1. **Known product-integration gates** already documented by maintainers: R11–R13 live state, durable share/revoke writes, two-user isolation, restart/reconnect identity, cross-transport parity, external-client interoperability, and later R14 collaboration surface.
2. **Protocol/security defects in this exact head** that are not solved merely by waiting for R11/R12. Several violate the same MCP `2025-03-26` version the server announces.

## Positive findings worth preserving

- Matching/business internals remain out of the HTTP framing layer.
- `discover_resonance` preserves the full R8 structured result rather than collapsing it to prose.
- The SVG visual is derived from already-consented discovery fields and escapes text before insertion.
- PKCE verification is S256-only and uses constant-time comparison.
- Authentication is required on `/mcp`; tokens are generated at runtime rather than committed.
- Local-host default binding is appropriate for a development server.
- The README explicitly labels the OAuth implementation as demo-grade instead of pretending it is a production IdP.

## Acceptance gaps already known from the mission/review history

These are confirmed but are not new findings from this reviewer:

- `ProductService()` defaults to the R7 fixture service rather than the future accepted R11/R12/R13 product state.
- `get_thought(subject, thought_id)` proves only that a subject exists; it does not enforce object ownership/share policy.
- remote create/update/share/revoke persistence is absent; `ingest_thought` produces a graph but does not durably publish it.
- MCP session IDs are stored globally rather than bound to authenticated subject/client state.
- OAuth identity is a static demo-user scaffold rather than an accepted authenticated/consenting identity flow.
- request bodies are read from caller-supplied `Content-Length` before the service-level context size cap applies.
- generic MCP Inspector plus OpenAI/Anthropic remote-client evidence is absent.

Those alone are sufficient to keep R15 pending. The findings below add exact protocol/security work that should be corrected in the transport foundation itself.

# New exact-head findings

## F1 — BLOCKER — missing `Origin` validation violates advertised Streamable HTTP version

**Surface:** `src/remote/server.py`, `StreamableHTTPHandler.do_POST()` / request handling.

The server never validates the HTTP `Origin` header. The MCP `2025-03-26` Streamable HTTP security requirements state that servers **MUST validate `Origin` on all incoming connections** to prevent DNS-rebinding attacks. This is an original requirement of the advertised protocol version, not a later R12B invention.

**Impact:** a local MCP service can be targeted by a hostile web origin through DNS rebinding; hosted origin policy is also undefined.

**Required fix:** implement an explicit allowed-origin policy before parsing/processing MCP/auth requests. Local development should permit only the intended localhost/null cases by documented policy; hosted deployments should allowlist configured HTTPS origin(s). Add deterministic rejected-origin tests.

## F2 — BLOCKER — advertised `2025-03-26` server does not accept JSON-RPC batches

**Surface:** `src/remote/server.py`, `do_POST()` -> `json.loads()` -> `RemoteMCP.handle()`.

The `2025-03-26` Streamable HTTP POST contract permits a single JSON-RPC message **or an array batch**. `json.loads()` can therefore validly return a list. `RemoteMCP.handle()` immediately assumes a mapping and calls `message.get(...)`; a valid batch will fail with `AttributeError` outside the JSON-RPC error-mapping path.

This protocol version explicitly included JSON-RPC batching. If the implementation wants a version in which batching is not part of the protocol, it must negotiate/implement that later version consistently rather than announcing `2025-03-26`.

**Required fix:** implement request/notification batch dispatch and correct HTTP response semantics for mixed request/notification batches, or intentionally move to a compatible later protocol version and update transport/auth behavior/tests accordingly.

## F3 — BLOCKER — OAuth endpoints are not discoverable by a conforming `2025-03-26` MCP client

**Surface:** `src/remote/server.py`, routes `/oauth/authorize` and `/oauth/token`; no authorization-server metadata route.

The `2025-03-26` authorization spec says clients first perform RFC 8414 authorization-server metadata discovery. A server without metadata must expose fallback paths relative to the authorization base URL:

- `/authorize`
- `/token`
- `/register` where Dynamic Client Registration is supported

PR #93 exposes `/oauth/authorize` and `/oauth/token` and no metadata document that advertises those non-default paths. A generic MCP client following the advertised protocol therefore has no standards-defined way to discover this OAuth surface.

**Required fix:** preferably expose valid RFC 8414 metadata at `/.well-known/oauth-authorization-server` that names the actual endpoints, plus the chosen client-registration strategy. Alternatively use the specified fallback paths. Validate with a generic MCP client rather than only a repository-specific urllib test.

## F4 — BLOCKER — OAuth redirect URI validation is insufficient and the committed happy-path test proves an invalid URI is accepted

**Surface:** `src/remote/auth.py::issue_code`; `tests/test_remote_mcp.py::test_oauth_pkce_flow_yields_working_token`.

`issue_code()` stores whatever `redirect_uri` string the caller supplies. The happy-path test explicitly uses `http://cb`. The MCP `2025-03-26` authorization requirements say servers MUST validate redirect URIs and that redirect URIs MUST be **localhost URLs or HTTPS URLs**.

The current test therefore proves acceptance of a redirect URI that does not meet the advertised authorization contract.

**Required fix:** perform strict registered/client-bound redirect validation before issuing the authorization code. Reject arbitrary HTTP hosts; allow HTTPS and tightly defined loopback redirect forms as appropriate. Add negative tests for `http://evil.example`, scheme confusion, userinfo, malformed ports, and redirect substitution.

Related ordering defect: `_authorize()` calls `issue_code()` before checking `code_challenge_method == "S256"`, so an invalid-method request can allocate an otherwise usable server-side code record before returning an error. Validate the entire authorization request first, then mint state.

## F5 — MAJOR — session enforcement is bypassed for notifications and HTTP session semantics are inconsistent

**Surface:** `src/remote/server.py::RemoteMCP.handle()`.

The function returns early for `notifications/initialized` and then for **any message with no `id`** before verifying `session_id in self.sessions`. Once the server has elected to issue an `Mcp-Session-Id`, the `2025-03-26` transport requires clients to include it on all subsequent HTTP requests. The current control flow silently accepts post-initialize notifications without validating the session.

For request messages, missing/unknown sessions are returned as HTTP 200 containing JSON-RPC `-32600`. The protocol says a server requiring a session SHOULD return HTTP 400 when the session header is missing; after a session is terminated it MUST return HTTP 404 so clients know to initialize again.

**Required fix:** validate the bound session before accepting any post-initialize request/notification; use transport-level 400/404 behavior consistently; implement explicit expiry/termination state. This should converge with the #89 requirement to bind session state to authenticated subject/client and current authorization-grant generation.

## F6 — MAJOR — session/code/token lifecycle permits unbounded state growth and lacks revocation/expiry controls

**Surface:** `src/remote/server.py::RemoteMCP.sessions`; `src/remote/auth.py::AuthStore`.

- Every authenticated `initialize` adds a random session ID to an unbounded `set` with no TTL or cleanup.
- Authorization codes are removed only on an attempted exchange. Expired, never-exchanged codes remain indefinitely.
- Bearer tokens have no expiry, rotation, or revocation mechanism.
- `/oauth/authorize` is not rate-limited through `ProductService`, so code allocation is a separate unbounded state surface.

The authorization spec recommends token expiration/rotation, and current #89 explicitly requires session expiry/revocation/cleanup for the pilot.

**Required fix:** bounded/expiring session and authorization records, token revocation/expiry appropriate to the pilot, auth-endpoint rate limits, deterministic cleanup, and tests proving stale IDs/codes/tokens fail closed.

## F7 — MAJOR correctness — product rate limiting double-charges some tools

**Surface:** `src/remote/service.py` and `src/remote/server.py::_dispatch()`.

`ProductService.ingest()`, `compare()`, and `get_thought()` each call `_require(subject)`, which consumes one rate-limit token. `_dispatch()` then calls `self.service.identity(subject)` for those same tool invocations, and `identity()` calls `_require(subject)` again. Those tools therefore consume two quota units per logical invocation, while `discover_resonance` consumes one.

The current rate-limit test does not assert per-call token accounting and can mask this asymmetry.

**Impact:** quota behavior depends on response-decoration code rather than action cost/policy, producing premature throttling and making audit/retry behavior unpredictable.

**Required fix:** authenticate/authorize/rate-limit each logical operation at one explicit decision point. Provenance/identity metadata lookup must not independently spend the operation quota. Add a test that one tool invocation consumes exactly the documented amount.

## F8 — MEDIUM security — unexpected exception messages are reflected to remote clients

**Surface:** `src/remote/server.py::_call()`.

The generic exception branch returns `f"{type(exc).__name__}: {exc}"` over the wire. As R11/R12/R13 introduce database/auth/service internals, exception strings can contain implementation details or data not intended for a remote caller.

**Required fix:** return a stable opaque internal-error response with a correlation/request ID; keep minimized diagnostic details only in server-side logs. Explicit validation/auth errors can remain structured but must not leak private payloads.

# Required regression evidence before the next exact-head review

At minimum, add/reproduce these executable cases in addition to the mission's live-product acceptance tests:

1. **Origin allowlist** — malicious `Origin: https://evil.example` is rejected before MCP processing; intended deployment origin succeeds.
2. **Batch conformance** — for `2025-03-26`, a valid batch with requests/notifications receives correct per-message semantics, including a notification-only 202 case. If changing protocol version instead, demonstrate correct version negotiation and matching tests.
3. **OAuth discovery** — a generic client can discover the authorization server from the MCP base URL without repository-specific endpoint knowledge.
4. **Redirect validation** — reject `http://cb` / arbitrary HTTP hosts; accept only the intended HTTPS/loopback forms and registered redirect.
5. **Session enforcement** — post-initialize notifications without/wrong session fail; valid session succeeds; terminated/expired session yields transport behavior that causes a client to reinitialize.
6. **Cross-subject replay** — a session minted under user A cannot be used with user B's bearer credential.
7. **Lifecycle bounds** — expired code/session/token cleanup and revocation are deterministic; repeated initialize/authorize cannot grow state without bound.
8. **Rate accounting** — one logical call consumes one documented policy decision/quota debit; adding provenance metadata does not double-charge.
9. **Error minimization** — forced internal exception returns an opaque correlation ID, not raw internal exception text/private data.
10. **Existing full R15 gates** — two live users, object-scoped authorization, durable create/update/share/revoke in R11 state, restart/reconnect, UI/WebMCP/remote result parity, generic Inspector and available OpenAI/Anthropic interop, full regression suite.

## Suggested clone-capable commands

These are commands for the next reviewer/CI runner; they are **not claimed as executed by this review**:

```bash
python3 -m compileall -q src tests
python3 -m unittest tests.test_remote_mcp -v
python3 -m unittest discover -s tests -v
git diff --check <accepted-base>...<candidate-head>
```

Add targeted tests for F1–F9 before relying on the generic suite.

## Scope timing note

The canonical author submitted PR #93 before some later #89 security addenda were recorded. This review does not retroactively accuse the author of ignoring requirements that did not yet exist. However, F1–F5 are grounded directly in the MCP `2025-03-26` protocol/auth contract that the PR itself announces, and F6–F9 are necessary hardening/correctness findings for the current product gate. The later #89 session/grant requirements reinforce, rather than create, several of these concerns.

## Handoff

Preserve the good transport-neutral shape, structured discovery result, and honest foundation labeling. Do not attempt to patch final authorization inside transport handlers. R11/R12/R12B should provide the authoritative subject/object/consent/grant decisions; R15 should bind transport sessions to those decisions and implement the MCP wire contract exactly.
