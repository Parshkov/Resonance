# P1 — HTTP surface checks (HEAD 3c7dc80)

Origin: https://resonance-production-cfe3.up.railway.app · run 2026-09-04T15:41:05Z

## HEAD /
```
HTTP/1.1 200 Connection Established

HTTP/2 200 
content-security-policy: default-src 'self'; frame-ancestors 'none'
content-type: text/html; charset=utf-8
cross-origin-opener-policy: same-origin
date: Fri, 04 Sep 2026 15:41:05 GMT
permissions-policy: tools=(self)
referrer-policy: no-referrer
server: railway-hikari
x-content-type-options: nosniff
x-railway-request-id: cZW0wHjfRJq4i1vUg4a9AQ
content-length: 12875
x-hikari-trace: iad1.dh1s
x-railway-edge: iad1

```
## HEAD /webmcp.mjs
```
HTTP/1.1 200 Connection Established

HTTP/2 200 
content-security-policy: default-src 'self'; frame-ancestors 'none'
content-type: text/javascript; charset=utf-8
cross-origin-opener-policy: same-origin
date: Fri, 04 Sep 2026 15:41:06 GMT
permissions-policy: tools=(self)
referrer-policy: no-referrer
server: railway-hikari
x-content-type-options: nosniff
x-railway-request-id: EeC4iy_ZRKObnwRXaP71AA
content-length: 12522
x-hikari-trace: iad1.fp5t
x-railway-edge: iad1

```
## HEAD /mcp
```
HTTP/1.1 200 Connection Established

HTTP/2 405 
allow: POST, DELETE
content-security-policy: default-src 'self'; frame-ancestors 'none'
cross-origin-opener-policy: same-origin
date: Fri, 04 Sep 2026 15:41:06 GMT
permissions-policy: tools=(self)
referrer-policy: no-referrer
server: railway-hikari
x-content-type-options: nosniff
x-railway-request-id: -fnHrMNSQYSzK5PbFFmdQQ
content-length: 0
x-hikari-trace: iad1.dh1s
x-railway-edge: iad1

```
## GET /oauth/consent.css
```
HTTP/1.1 200 Connection Established

HTTP/2 200 
cache-control: public, max-age=3600
content-security-policy: default-src 'self'; frame-ancestors 'none'
content-type: text/css; charset=utf-8
cross-origin-opener-policy: same-origin
date: Fri, 04 Sep 2026 15:41:06 GMT
permissions-policy: tools=(self)
referrer-policy: no-referrer
server: railway-hikari
x-content-type-options: nosniff
x-railway-request-id: u2CKZU8ATLutD1gmyCLmYg
content-length: 2687
x-hikari-trace: iad1.dh1s
x-railway-edge: iad1
vary: accept-encoding

```
## GET /api/product/health
```
{"ok": true, "mode": "live", "freshness": {"db_generation": 174, "serving_generation": 174, "index_current": true, "engine_snapshot": "bb9312d482b1cd0dfd401a6998fae3ea08fd9ebc818f661e84b539bc526212e1"}}
```
