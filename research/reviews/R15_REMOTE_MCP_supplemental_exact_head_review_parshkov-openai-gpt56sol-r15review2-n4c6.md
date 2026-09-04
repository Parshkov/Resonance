# R15 Remote MCP — supplemental exact-head review of PR #93

## Review identity and provenance

- `base_mission`: `R15-REMOTE-MCP`
- `review_run_id`: `R15-REMOTE-MCP-REVIEW-N4C6`
- `agent_id`: `parshkov-openai-gpt56sol-r15review2-n4c6`
- `human_sponsor`: `Parshkov`
- `provider`: OpenAI
- `model`: GPT-5.6 Sol
- `reviewed_pull_request`: https://github.com/Parshkov/Resonance/pull/93
- `reviewed_exact_head`: `4a136ff0a7a1bb59d08adf772c380c5a5cb1f77d`
- `canonical_author`: `dima2010-anthropic-fable5-7328` / Anthropic Claude Fable 5
- `execution_environment`: ChatGPT connected session with GitHub connector; local analysis sandbox without a network GitHub checkout
- `mission_modified`: no
- `blind_status`: non-blind; no blind group applies

## Independence disclosure

This is a **supplemental**, not blind, review. Before starting it I inspected the earlier OpenAI exact-head review in PR #107 (`R15-REMOTE-MCP-REVIEW-S9K4`). I therefore do **not** claim independence from that reviewer. I remain independent from the canonical Anthropic implementation author, and I intentionally exclude findings already recorded in #107 except where needed to distinguish a new failure mode.

PR #107 already covers missing Origin validation, batch receive support, OAuth discovery/default-route problems, redirect-URI validation, notification/session handling, unbounded session/auth lifecycle, double rate charging, and raw internal exception reflection. This artifact adds only findings not already present there.

## Evidence boundary

I re-read PR #93 metadata and all seven changed files at exact head `4a136ff0a7a1bb59d08adf772c380c5a5cb1f77d` and checked the protocol version advertised by the implementation against the official MCP `2025-03-26` lifecycle/authorization contracts and the OAuth authorization-code flow they incorporate.

References:

- https://modelcontextprotocol.io/specification/2025-03-26/basic/lifecycle
- https://modelcontextprotocol.io/specification/2025-03-26/basic/transports
- https://modelcontextprotocol.io/specification/2025-03-26/basic/authorization
- https://www.rfc-editor.org/rfc/rfc6749.html

The sandbox cannot obtain a network checkout, so I do **not** claim an independent full-suite run. I did run focused standalone Python reproductions using the exact reviewed control flow for the authorization-code consumption finding and malformed-`params` dispatch failure. Those reproductions are described below and are not substitutes for repository tests.

## Verdict

**REQUEST_CHANGES remains correct.** PR #93 should stay a useful R15 transport foundation, not an acceptance candidate. The prior review is already sufficient to block acceptance; the four findings below add interoperability/lifecycle/robustness work that should be fixed in the same transport revision rather than deferred to R11/R12 integration.

# Additional exact-head findings

## N1 — BLOCKER — the implemented OAuth “authorization endpoint” is not an interoperable authorization-code endpoint

**Surface:** `src/remote/server.py::do_GET`, `do_POST`, `_authorize`; `tests/test_remote_mcp.py::test_oauth_pkce_flow_yields_working_token`.

This is distinct from PR #107's discovery/path finding. Even if metadata were added and the endpoint renamed to `/authorize`, the actual wire flow is still custom rather than OAuth authorization-code flow:

- `do_GET()` supports only `/mcp`; an OAuth authorization endpoint cannot be reached with the required browser GET flow.
- `_authorize()` is only invoked through `POST /oauth/authorize`.
- it does not require or inspect `response_type=code`.
- it does not accept/preserve OAuth `state`.
- it accepts a caller-supplied `user` field as the authorization decision.
- on success it returns HTTP 200 JSON `{"code": ...}` instead of redirecting the resource-owner user agent back to the validated `redirect_uri` with `code` (and `state`, if supplied).

MCP `2025-03-26` says HTTP authorization implementations use OAuth 2.1 and describes a human completing the authorization flow through a browser. The OAuth authorization-code contract requires the authorization endpoint to support GET, requires `response_type=code`, and returns the authorization response through the client's redirection endpoint; `state` must be echoed if present.

**Impact:** a generic MCP/OAuth client cannot complete authorization against this server even after the previously reported metadata/default-path defect is fixed. The repository-specific urllib test passes only because it implements the same private POST+JSON convention.

**Required fix:** implement a real browser authorization endpoint (or delegate to a real authorization server), with GET request parsing, authenticated resource-owner/consent interaction, `response_type=code`, client/redirect registration, state round-trip, 302 redirect response, and the existing PKCE binding. Then validate it with a generic OAuth/MCP client rather than a repository-specific helper.

## N2 — BLOCKER — `initialize` accepts an invalid lifecycle shape and therefore does not actually negotiate protocol/capabilities

**Surface:** `src/remote/server.py::RemoteMCP.handle`; `tests/test_remote_mcp.py::_init_session`.

The advertised MCP lifecycle requires the client's first `initialize` request to carry:

- `protocolVersion`;
- `capabilities`;
- `clientInfo`.

`RemoteMCP.handle()` ignores `params` entirely for `initialize`, immediately creates a session, and always answers with `PROTOCOL_VERSION = "2025-03-26"`. The committed test helper proves this behavior by initializing with only:

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
```

and expecting success.

There is a second edge case in the same branch: because the `initialize` special case executes before the generic `msg_id is None` notification path, an `initialize` message **without an id** is accepted and produces a response with `id: null`. MCP initialization must be a request; MCP request IDs are string/number, while notifications have no response.

**Impact:** protocol version compatibility and client capability negotiation are not being performed despite the server claiming MCP lifecycle compliance. Malformed/non-MCP clients can mint sessions, and tests currently enshrine the malformed shape.

**Required fix:** strictly validate `InitializeRequest`, require the mandatory fields and a valid request id, negotiate supported versions, record negotiated client capabilities/session state, and reject malformed initialization with the correct JSON-RPC error. Update every HTTP test to use a protocol-valid initialize request.

## N3 — MAJOR robustness / authenticated request DoS — malformed `params` can escape the JSON-RPC error boundary

**Surface:** `src/remote/server.py::RemoteMCP.handle`, `_call`, `StreamableHTTPHandler.do_POST`.

After JSON decoding, the code does:

```python
params = message.get("params") or {}
...
return self._call(msg_id, params, subject), session_id
```

and `_call()` begins with:

```python
name = params.get("name")
arguments = dict(params.get("arguments") or {})
```

Those lines are **outside** `_call()`'s `try` block. A truthy JSON scalar such as `"params":"oops"` or `"params":7` therefore raises `AttributeError` before the implementation can map it to `INVALID_PARAMS`. `do_POST()` also has no exception guard around `self.core.handle(...)`, so the request handler fails rather than returning a JSON-RPC error.

Focused standalone reproduction of the exact control flow produced:

```text
params="oops" -> AttributeError: 'str' object has no attribute 'get'
params=7      -> AttributeError: 'int' object has no attribute 'get'
```

**Impact:** any authenticated caller can repeatedly force abnormal request-thread termination with a small malformed JSON body. More importantly, the transport does not preserve its advertised JSON-RPC error semantics at the untrusted boundary.

**Required fix:** validate top-level message and `params` types before dispatch; keep all untrusted-shape handling inside a transport error boundary; return `INVALID_REQUEST`/`INVALID_PARAMS` without exposing implementation exceptions. Add real HTTP tests for scalar/array/null `params`, scalar top-level JSON, missing method, and malformed tool arguments.

## N4 — MEDIUM availability / auth-state correctness — failed code exchange consumes the authorization code before verifier/client validation

**Surface:** `src/remote/auth.py::AuthStore.exchange_code`.

The function starts with:

```python
record = self.codes.pop(code, None)
```

and only afterwards validates expiry, redirect/client binding, and the PKCE verifier. Therefore **any failed exchange attempt permanently destroys the authorization code**, including one with the wrong verifier or wrong client/redirect.

Focused standalone reproduction using the exact method logic:

```text
code initially exists: True
wrong verifier: PKCE verification failed
code after failed exchange exists: False
legitimate retry with correct verifier: invalid or expired authorization code
```

This finding is not presented as a direct MCP MUST-level violation; one-time-code implementations may deliberately adopt aggressive invalidation policies. Here, however, the behavior is undocumented, untested as policy, and creates a simple authorization-completion denial if a code is observed and probed before the legitimate client exchange.

**Required fix:** make code-consumption policy explicit. Prefer validating client/redirect/PKCE and atomically marking the code consumed only for a valid exchange, while separately detecting/rejecting replay; if fail-on-any-attempt is intentional, document that threat tradeoff and add deterministic tests so it is not accidental behavior.

# Regression evidence requested for the next head

In addition to all tests requested by PR #107 and the full R15 product gates, add these cases:

1. **Standards authorization flow:** GET authorization request with `response_type=code`, state, PKCE, registered client/redirect -> authenticated authorization -> 302 to the exact redirect URI containing code + unchanged state -> token exchange succeeds.
2. **Initialization validation:** missing `protocolVersion`, `capabilities`, or `clientInfo` is rejected; initialize notification/no-id is rejected; supported-version negotiation is recorded and returned correctly.
3. **Malformed parameter boundary:** authenticated `tools/call` with scalar/string/list invalid `params` returns deterministic JSON-RPC error and never drops the HTTP handler.
4. **Authorization-code state:** wrong verifier/client/redirect behavior follows an explicit tested consumption/replay policy; legitimate valid exchange behavior is deterministic after failed probes.

## Positive findings preserved

This supplemental review does not change the useful parts already identified: transport/business separation, complete structured discovery payload, escaped SVG labels, localhost default binding, runtime-generated secrets, and honest labeling of the OAuth layer as demo-grade. The recommendation is to preserve those shapes while replacing the private auth/lifecycle shortcuts with interoperable protocol behavior.

## Submission/handoff

No canonical implementation file is modified by this review. The correct next step for PR #93 is still revision, not merge. Once R11/R12/R12B/R13/R14 service dependencies are accepted, R15 should additionally bind its session/auth layer to the canonical subject/object/consent service and rerun both the product acceptance gates and the full MCP transport/auth conformance set.
