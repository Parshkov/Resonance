# P1 — HEAD checks on https://resonance-production-cfe3.up.railway.app

Captured 2026-09-04T15:11:36Z at HEAD 01193f1.

## `/`

```
$ curl -sS -I https://resonance-production-cfe3.up.railway.app/
HTTP/1.1 200 Connection Established
HTTP/2 200 
content-type: text/html; charset=utf-8
content-length: 12875

$ curl -sS -D - -o /dev/null https://resonance-production-cfe3.up.railway.app/   (GET)
HTTP/1.1 200 Connection Established
HTTP/2 200 
content-type: text/html; charset=utf-8
content-length: 12875
```

## `/api/product/health`

```
$ curl -sS -I https://resonance-production-cfe3.up.railway.app/api/product/health
HTTP/1.1 200 Connection Established
HTTP/2 200 
content-type: application/json; charset=utf-8
content-length: 202

$ curl -sS -D - -o /dev/null https://resonance-production-cfe3.up.railway.app/api/product/health   (GET)
HTTP/1.1 200 Connection Established
HTTP/2 200 
content-type: application/json; charset=utf-8
content-length: 202
```

## `/webmcp.mjs`

```
$ curl -sS -I https://resonance-production-cfe3.up.railway.app/webmcp.mjs
HTTP/1.1 200 Connection Established
HTTP/2 200 
content-type: text/javascript; charset=utf-8
content-length: 12522

$ curl -sS -D - -o /dev/null https://resonance-production-cfe3.up.railway.app/webmcp.mjs   (GET)
HTTP/1.1 200 Connection Established
HTTP/2 200 
content-type: text/javascript; charset=utf-8
content-length: 12522
```

## `/mcp`

```
$ curl -sS -I https://resonance-production-cfe3.up.railway.app/mcp
HTTP/1.1 200 Connection Established
HTTP/2 405 
allow: POST, DELETE
content-length: 0

```

