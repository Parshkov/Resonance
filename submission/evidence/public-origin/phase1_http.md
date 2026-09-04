# Phase 1 — raw HTTP evidence against public origin

Origin: https://resonance-production-cfe3.up.railway.app
Captured: 2026-09-04T06:14:11Z
Repo HEAD: 4ab28a30f986478562a88e1e1e6a83c81ef7bda9


## 1a GET /api/product/health

```
HTTP/1.1 200 Connection Established

HTTP/2 200 
content-security-policy: default-src 'self'; frame-ancestors 'none'
content-type: application/json; charset=utf-8
cross-origin-opener-policy: same-origin
date: Fri, 04 Sep 2026 06:14:11 GMT
permissions-policy: tools=(self)
referrer-policy: no-referrer
server: railway-hikari
x-content-type-options: nosniff
x-railway-request-id: A29AcirzQLy9ieGRezItjw
content-length: 200
x-hikari-trace: iad1.fp5t
x-railway-edge: iad1

{"ok": true, "mode": "live", "freshness": {"db_generation": 78, "serving_generation": 78, "index_current": true, "engine_snapshot": "f7f839d595712aa5467cc12fd91b19c44ccc944f2f0a415f466b4240f8a05892"}}
```

## 1b POST /mcp initialize, NO Authorization (expect 401 + WWW-Authenticate resource_metadata)

```
HTTP/1.1 200 Connection Established

HTTP/2 401 
content-security-policy: default-src 'self'; frame-ancestors 'none'
content-type: application/json; charset=utf-8
cross-origin-opener-policy: same-origin
date: Fri, 04 Sep 2026 06:14:12 GMT
permissions-policy: tools=(self)
referrer-policy: no-referrer
server: railway-hikari
www-authenticate: Bearer realm="resonance", resource_metadata="https://resonance-production-cfe3.up.railway.app/.well-known/oauth-protected-resource"
x-content-type-options: nosniff
x-railway-request-id: 1d6oXhkBRsqLMzfvHn5Ytg
content-length: 254
x-hikari-trace: iad1.dh1s
x-railway-edge: iad1

{"error": "authentication_failed", "message": "authorize this client through https://resonance-production-cfe3.up.railway.app/.well-known/oauth-protected-resource (hosted clients do this automatically), or send an MCP key as Authorization: Bearer <key>"}
```

## 1c GET /.well-known/oauth-protected-resource

```
HTTP/1.1 200 Connection Established

HTTP/2 200 
cache-control: no-store
content-security-policy: default-src 'self'; frame-ancestors 'none'
content-type: application/json
cross-origin-opener-policy: same-origin
date: Fri, 04 Sep 2026 06:14:12 GMT
permissions-policy: tools=(self)
referrer-policy: no-referrer
server: railway-hikari
x-content-type-options: nosniff
x-railway-request-id: 5C1mKRgtTCKv0Za_Cx5-qw
content-length: 319
x-hikari-trace: iad1.trg5
x-railway-edge: iad1
vary: accept-encoding

{"resource": "https://resonance-production-cfe3.up.railway.app/mcp", "authorization_servers": ["https://resonance-production-cfe3.up.railway.app"], "scopes_supported": ["resonance", "offline_access"], "bearer_methods_supported": ["header"], "resource_documentation": "https://resonance-production-cfe3.up.railway.app/"}
```

## 1d GET /.well-known/oauth-authorization-server

```
HTTP/1.1 200 Connection Established

HTTP/2 200 
cache-control: no-store
content-security-policy: default-src 'self'; frame-ancestors 'none'
content-type: application/json
cross-origin-opener-policy: same-origin
date: Fri, 04 Sep 2026 06:14:12 GMT
permissions-policy: tools=(self)
referrer-policy: no-referrer
server: railway-hikari
x-content-type-options: nosniff
x-railway-request-id: nMQNv1KJRDSrPDsxqmzx2A
content-length: 767
x-hikari-trace: iad1.dh1s
x-railway-edge: iad1
vary: accept-encoding

{"issuer": "https://resonance-production-cfe3.up.railway.app", "authorization_endpoint": "https://resonance-production-cfe3.up.railway.app/oauth/authorize", "token_endpoint": "https://resonance-production-cfe3.up.railway.app/oauth/token", "registration_endpoint": "https://resonance-production-cfe3.up.railway.app/oauth/register", "revocation_endpoint": "https://resonance-production-cfe3.up.railway.app/oauth/revoke", "response_types_supported": ["code"], "grant_types_supported": ["authorization_code", "refresh_token"], "code_challenge_methods_supported": ["S256"], "token_endpoint_auth_methods_supported": ["none"], "revocation_endpoint_auth_methods_supported": ["none"], "scopes_supported": ["resonance", "offline_access"], "resource_indicators_supported": true}
```

## 1e GET /mcp (expect 405)

```
HTTP/1.1 200 Connection Established

HTTP/2 405 
allow: POST, DELETE
content-security-policy: default-src 'self'; frame-ancestors 'none'
cross-origin-opener-policy: same-origin
date: Fri, 04 Sep 2026 06:14:12 GMT
permissions-policy: tools=(self)
referrer-policy: no-referrer
server: railway-hikari
x-content-type-options: nosniff
x-railway-request-id: 3XX-rAL5Q_6soy7cBT7zVQ
content-length: 0
x-hikari-trace: iad1.fp5t
x-railway-edge: iad1


```

## 1e GET /oauth/authorize with no params (record status)

```
HTTP/1.1 200 Connection Established

HTTP/2 400 
content-security-policy: default-src 'self'; frame-ancestors 'none'
content-type: application/json
cross-origin-opener-policy: same-origin
date: Fri, 04 Sep 2026 06:14:12 GMT
permissions-policy: tools=(self)
referrer-policy: no-referrer
server: railway-hikari
x-content-type-options: nosniff
x-railway-request-id: lhQ3PAQ7SD-u1O0DBT7zVQ
content-length: 71
x-hikari-trace: iad1.fp5t
x-railway-edge: iad1

{"error": "invalid_request", "error_description": "client_id required"}
```

## 1f GET / (status, headers, title, webmcp.mjs reference)

```
HTTP/1.1 200 Connection Established

HTTP/2 200 
content-security-policy: default-src 'self'; frame-ancestors 'none'
content-type: text/html; charset=utf-8
cross-origin-opener-policy: same-origin
date: Fri, 04 Sep 2026 06:14:13 GMT
permissions-policy: tools=(self)
referrer-policy: no-referrer
server: railway-hikari
x-content-type-options: nosniff
x-railway-request-id: Wx-yIIE0QsaomZuYqmzx2A
content-length: 12875
x-hikari-trace: iad1.fp5t
x-railway-edge: iad1
vary: accept-encoding


--- <title>:
<title>Resonance — Visual Discovery</title>
--- lines referencing webmcp.mjs:
240:  <script type="module" src="/webmcp.mjs"></script>
--- body bytes: 12875
```

## 1f GET /webmcp.mjs (status, headers; grep document.modelContext / registerTool)

```
HTTP/1.1 200 Connection Established

HTTP/2 200 
content-security-policy: default-src 'self'; frame-ancestors 'none'
content-type: text/javascript; charset=utf-8
cross-origin-opener-policy: same-origin
date: Fri, 04 Sep 2026 06:14:13 GMT
permissions-policy: tools=(self)
referrer-policy: no-referrer
server: railway-hikari
x-content-type-options: nosniff
x-railway-request-id: 5bVztXoOSQ-pGGQ3ezItjw
content-length: 9753
x-hikari-trace: iad1.dh1s
x-railway-edge: iad1
vary: accept-encoding


--- bytes: 9753
--- count 'document.modelContext': 1
--- count 'registerTool': 2
--- matching lines (first 12):
234:  const modelContext = document.modelContext || navigator.modelContext;
235:  if (!modelContext?.registerTool) {
242:      await modelContext.registerTool(tool, {signal: registrationController.signal});
```

## 1g POST /mcp with bogus bearer 'nope' (expect 401)

```
HTTP/1.1 200 Connection Established

HTTP/2 401 
content-security-policy: default-src 'self'; frame-ancestors 'none'
content-type: application/json; charset=utf-8
cross-origin-opener-policy: same-origin
date: Fri, 04 Sep 2026 06:14:13 GMT
permissions-policy: tools=(self)
referrer-policy: no-referrer
server: railway-hikari
www-authenticate: Bearer realm="resonance", error="invalid_token", resource_metadata="https://resonance-production-cfe3.up.railway.app/.well-known/oauth-protected-resource"
x-content-type-options: nosniff
x-railway-request-id: OFFhSggJR4uWZ80yjVra_w
content-length: 254
x-hikari-trace: iad1.dh1s
x-railway-edge: iad1

{"error": "authentication_failed", "message": "authorize this client through https://resonance-production-cfe3.up.railway.app/.well-known/oauth-protected-resource (hosted clients do this automatically), or send an MCP key as Authorization: Bearer <key>"}
```
