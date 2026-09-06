"""Phase 4 — OAuth / MCP negatives against the public origin. Stdlib only; never prints tokens."""
from __future__ import annotations
import json, os, re, sys
from datetime import datetime, timezone
from urllib.parse import urlencode
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from ops import oauth_smoke  # noqa: E402

RESOURCE = sys.argv[1] if len(sys.argv) > 1 else "https://resonance-production-cfe3.up.railway.app/mcp"


class _CI(dict):
    def __init__(self, items):
        super().__init__((k.lower(), v) for k, v in dict(items).items())
    def get(self, key, default=None):
        return super().get(key.lower(), default)


_orig = oauth_smoke.Smoke._req
def _req(self, url, **kw):
    s, h, b = _orig(self, url, **kw); return s, _CI(h), b
oauth_smoke.Smoke._req = _req

rows = []
def rec(name, ok, **d):
    rows.append({"check": name, "pass": bool(ok), **d}); print(f"[{'PASS' if ok else 'FAIL'}] {name} {json.dumps(d, default=str)}")

s = oauth_smoke.Smoke(RESOURCE, auto_consent=True, verbose=False)
st, hdr, _ = s._rpc("ping", mid=1, bearer=None)
prm_url = re.search(r'resource_metadata="([^"]+)"', hdr.get("WWW-Authenticate", "")).group(1)
_, _, prm = s._json(prm_url); issuer = prm["authorization_servers"][0].rstrip("/")
_, _, s.meta = s._json(f"{issuer}/.well-known/oauth-authorization-server")
st, _, client = s._json(s.meta["registration_endpoint"], method="POST", headers={"Content-Type": "application/json"},
                        data=json.dumps({"client_name": "resonance-phase4-negatives", "redirect_uris": [oauth_smoke.REDIRECT_URI],
                                         "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
                                         "token_endpoint_auth_method": "none"}).encode())
s.client_id = client["client_id"]; rec("register client", st in (200, 201), status=st)

def tok(form): return s._token(form)
def good_form(code, **over):
    f = {"grant_type": "authorization_code", "code": code, "code_verifier": s._verifier,
         "redirect_uri": oauth_smoke.REDIRECT_URI, "client_id": s.client_id, "resource": s.resource}; f.update(over); return f

# 1 wrong PKCE verifier
code = s._authorize(quiet=True); st, _, t = tok(good_form(code, code_verifier="wrong-" + s._verifier))
rec("wrong PKCE verifier -> 400", st == 400, status=st, error=t.get("error"))
# 2 reused code (exchange ok, then replay)
code = s._authorize(quiet=True); st1, _, t1 = tok(good_form(code)); st2, _, t2 = tok(good_form(code))
rec("first exchange 200", st1 == 200 and bool(t1.get("access_token")), status=st1)
rec("reused code -> 400", st2 == 400, status=st2, error=t2.get("error"))
access1, refresh1 = t1.get("access_token"), t1.get("refresh_token")
# 3 wrong redirect_uri
code = s._authorize(quiet=True); st, _, t = tok(good_form(code, redirect_uri="http://evil.example/cb"))
rec("wrong redirect_uri -> 400", st == 400, status=st, error=t.get("error"))
# 4 wrong resource at token
code = s._authorize(quiet=True); st, _, t = tok(good_form(code, resource="https://evil.example/mcp"))
rec("wrong resource at token -> error", st in (400, 401) and bool(t.get("error")), status=st, error=t.get("error"))
# 5 refresh rotation: old refresh reuse -> 400
st, _, r1 = tok({"grant_type": "refresh_token", "refresh_token": refresh1, "client_id": s.client_id, "resource": s.resource})
rec("refresh grant 200", st == 200 and bool(r1.get("access_token")), status=st, rotated=bool(r1.get("refresh_token")) and r1.get("refresh_token") != refresh1)
st, _, r1b = tok({"grant_type": "refresh_token", "refresh_token": refresh1, "client_id": s.client_id, "resource": s.resource})
rec("old refresh token reuse -> 400", st == 400, status=st, error=r1b.get("error"))
access2, refresh2 = r1.get("access_token"), r1.get("refresh_token")
# does the rotated access token work, and did the old one survive?
def whoami(bearer):
    st, _, w = s._rpc("tools/call", {"name": "resonance_whoami", "arguments": {}}, mid=9, bearer=bearer)
    return st, bool(((w.get("result") or {}).get("structuredContent") or {}).get("user_id"))
st, ok = whoami(access2); rec("rotated access token works on /mcp", st == 200 and ok, status=st)
st, ok = whoami(access1); rows.append({"check": "original access token after refresh (observed)", "pass": True, "status": st, "authenticates": ok})
print(f"[INFO] original access token after refresh: status={st} authenticates={ok}")
# 6 revoke refresh then reuse -> 400 ; revoked access token on /mcp -> 401
rev = s.meta.get("revocation_endpoint")
st, _, body = s._json(rev, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"},
                      data=urlencode({"token": refresh2, "token_type_hint": "refresh_token", "client_id": s.client_id}).encode())
rec("revoke (refresh) -> 200", st == 200, status=st)
st, _, r3 = tok({"grant_type": "refresh_token", "refresh_token": refresh2, "client_id": s.client_id, "resource": s.resource})
rec("revoked refresh reuse -> 400", st == 400, status=st, error=r3.get("error"))
st, ok = whoami(access2)
rec("access token after refresh revocation on /mcp -> 401", st == 401 and not ok, status=st)
if st != 401:
    # revoke the access token explicitly and retest
    st_r, _, _ = s._json(rev, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"},
                         data=urlencode({"token": access2, "token_type_hint": "access_token", "client_id": s.client_id}).encode())
    st, ok = whoami(access2)
    rec("explicitly revoked access token on /mcp -> 401", st == 401 and not ok, revoke_status=st_r, status=st)
# 7 unknown Mcp-Session-Id -> 404 (fresh token)
code = s._authorize(quiet=True); st, _, t = tok(good_form(code)); bearer = t.get("access_token")
st, h, w = s._json(s.resource, method="POST", data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode(),
                   headers={"Content-Type": "application/json", "Authorization": f"Bearer {bearer}", "Mcp-Session-Id": "does-not-exist-000"})
rec("unknown Mcp-Session-Id on /mcp -> 404", st == 404, status=st, body_keys=sorted(w.keys()) if isinstance(w, dict) else None,
    error=(w.get("error") if isinstance(w, dict) else None))
st_i, h_i, _ = s._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "p4", "version": "0"}}, mid=1, bearer=bearer)
rows.append({"check": "initialize response carries Mcp-Session-Id (observed)", "pass": True, "status": st_i, "header_present": bool(h_i.get("Mcp-Session-Id"))})
print(f"[INFO] initialize: status={st_i} Mcp-Session-Id header present={bool(h_i.get('Mcp-Session-Id'))}")
# 8 query-string token must NOT authenticate
st, _, w = s._json(s.resource + "?access_token=" + bearer, method="POST",
                   data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode(),
                   headers={"Content-Type": "application/json"})
rec("/mcp?access_token=... does NOT authenticate (401)", st == 401, status=st)
# 9 bogus bearer
st, _, _ = s._rpc("ping", mid=1, bearer="nope"); rec("bogus bearer -> 401", st == 401, status=st)
# 10 GET authorize with wrong resource -> not a 200 consent page
s._verifier, ch = s._pkce_pair()
st, h, _ = s._req(s.meta["authorization_endpoint"] + "?" + urlencode({"response_type": "code", "client_id": s.client_id,
    "redirect_uri": oauth_smoke.REDIRECT_URI, "code_challenge": ch, "code_challenge_method": "S256", "state": "x",
    "resource": "https://evil.example/mcp"}))
loc = re.sub(r"code=[^&]+", "code=<redacted>", h.get("Location", "") or "")
rec("authorize with wrong resource -> error (302 invalid_target or 4xx)", st != 200 and ("invalid_target" in loc or 400 <= st < 500), status=st, location=loc[:160])
# 11 unregistered redirect_uri at authorize
st, h, _ = s._req(s.meta["authorization_endpoint"] + "?" + urlencode({"response_type": "code", "client_id": s.client_id,
    "redirect_uri": "http://evil.example/cb", "code_challenge": ch, "code_challenge_method": "S256", "state": "x", "resource": s.resource}))
rec("authorize with unregistered redirect_uri -> 4xx, no redirect", 400 <= st < 500 and not h.get("Location"), status=st)
# cleanup: revoke the last bearer's refresh
if t.get("refresh_token"):
    s._json(rev, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=urlencode({"token": t["refresh_token"], "token_type_hint": "refresh_token", "client_id": s.client_id}).encode())

passed = sum(r["pass"] for r in rows)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phase4_negatives.md")
blob = json.dumps(rows, indent=1, default=str)
for secret in (access1, access2, refresh1, refresh2, bearer, t.get("refresh_token")):
    assert not secret or secret not in blob
with open(out, "w") as f:
    f.write(f"# Phase 4 — negatives against public origin\n\nResource: {RESOURCE}\nRun: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n\n**{passed}/{len(rows)} checks passed** (rows marked observed carry no expectation)\n\n| check | result | detail |\n|---|---|---|\n")
    for r in rows:
        f.write(f"| {r['check']} | {'PASS' if r['pass'] else 'FAIL'} | `{json.dumps({k: v for k, v in r.items() if k not in ('check', 'pass')}, default=str)}` |\n")
print(f"\n{passed}/{len(rows)} passed -> {out}")
sys.exit(0 if passed == len(rows) else 1)
