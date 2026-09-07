# Phase 4 — negatives against public origin

Resource: https://resonance-production-cfe3.up.railway.app/mcp
Run: 2026-09-04T06:24:17Z

**18/20 checks passed** (rows marked observed carry no expectation)

| check | result | detail |
|---|---|---|
| register client | PASS | `{"status": 201}` |
| wrong PKCE verifier -> 400 | PASS | `{"status": 400, "error": "invalid_grant"}` |
| first exchange 200 | PASS | `{"status": 200}` |
| reused code -> 400 | PASS | `{"status": 400, "error": "invalid_grant"}` |
| wrong redirect_uri -> 400 | PASS | `{"status": 400, "error": "invalid_grant"}` |
| wrong resource at token -> error | PASS | `{"status": 400, "error": "invalid_target"}` |
| refresh grant 200 | PASS | `{"status": 200, "rotated": true}` |
| old refresh token reuse -> 400 | PASS | `{"status": 400, "error": "invalid_grant"}` |
| rotated access token works on /mcp | PASS | `{"status": 200}` |
| original access token after refresh (observed) | PASS | `{"status": 200, "authenticates": true}` |
| revoke (refresh) -> 200 | PASS | `{"status": 200}` |
| revoked refresh reuse -> 400 | PASS | `{"status": 400, "error": "invalid_grant"}` |
| access token after refresh revocation on /mcp -> 401 | FAIL | `{"status": 200}` |
| explicitly revoked access token on /mcp -> 401 | PASS | `{"revoke_status": 200, "status": 401}` |
| unknown Mcp-Session-Id on /mcp -> 404 | FAIL | `{"status": 200, "body_keys": ["id", "jsonrpc", "result"], "error": null}` |
| initialize response carries Mcp-Session-Id (observed) | PASS | `{"status": 200, "header_present": false}` |
| /mcp?access_token=... does NOT authenticate (401) | PASS | `{"status": 401}` |
| bogus bearer -> 401 | PASS | `{"status": 401}` |
| authorize with wrong resource -> error (302 invalid_target or 4xx) | PASS | `{"status": 302, "location": "http://127.0.0.1:8765/callback?error=invalid_target&error_description=resource+must+be+this+MCP+endpoint&state=x"}` |
| authorize with unregistered redirect_uri -> 4xx, no redirect | PASS | `{"status": 400}` |

## Notes on the two FAILs (honest reading)

1. **Refresh-token revocation does not cascade to the live access token.** After `POST /oauth/revoke` with the
   refresh token (200) the refresh token is dead (reuse -> 400 invalid_grant) but the access token issued alongside it
   still authenticated on `/mcp` (200). Revoking the access token explicitly (`token_type_hint=access_token`) then
   yields 401 on `/mcp`. RFC 7009 §2.1 says the server *SHOULD* also invalidate access tokens based on the same grant
   when a refresh token is revoked; production does not. Recorded as-is; no product code changed.
2. **Unknown `Mcp-Session-Id` returns 200, not 404.** The public `/mcp` is the stateless product bridge
   (`src/product/server.py::_handle_mcp`): `initialize` does not return an `Mcp-Session-Id` header and the header is
   ignored on later requests, so there is no session to be "unknown". The 404 behaviour the task expected lives in
   `src/remote/server.py`, which is not what production serves. Not an MCP spec violation (session ids are optional),
   but the expectation in the task did not hold.

Observed, no expectation asserted: the original access token stays valid after a refresh-token rotation until it
expires or is revoked.
