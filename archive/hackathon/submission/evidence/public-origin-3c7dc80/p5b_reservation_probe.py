import json, sys, datetime, os
from http.cookies import SimpleCookie
from urllib.error import HTTPError
from urllib.request import Request, urlopen
BASE = "https://resonance-production-cfe3.up.railway.app"
N = os.environ.get("NONCE", "x")
IMPLICIT_EXACT = ("Whenever the upstream degrades, thousands of clients notice timeouts at once and retry, "
                  "and the whole tier ends up saturated. We think jittered backoff would help.")
CUE_EXACT = ("A partial outage causes synchronized client retries. The retries cause request amplification, "
             "which leads to cascading saturation. Jittered backoff prevents the amplification.")
IMPLICIT_FRESH = IMPLICIT_EXACT + f" Ticket ref {N}-i."
CUE_FRESH = CUE_EXACT + f" Ticket ref {N}-c."
class Client:
    def __init__(self): self.cookie=None; self.csrf=None
    def request(self, method, path, body=None):
        h={"Content-Type":"application/json","Origin":BASE}
        if self.cookie: h["Cookie"]=self.cookie
        if self.csrf: h["X-Resonance-CSRF"]=self.csrf
        req=Request(BASE+path, data=json.dumps(body).encode() if body is not None else None, headers=h, method=method)
        try:
            with urlopen(req, timeout=30) as r:
                sc=r.headers.get("Set-Cookie")
                if sc:
                    m=SimpleCookie(sc).get("resonance_token")
                    if m is not None: self.cookie=f"resonance_token={m.value}"
                return r.status, json.loads(r.read().decode() or "{}")
        except HTTPError as e:
            return e.code, json.loads(e.read().decode() or "{}")
    def guest(self):
        st,p=self.request("POST","/api/product/guest",{}); self.csrf=p.get("csrf_token"); return st
def now(): return datetime.datetime.now(datetime.UTC).strftime("%H:%M:%SZ")
def show(label, st, body):
    keep={k:body.get(k) for k in ("error","message","input_kind","discoverable","draft_id","source_retention") if k in body}
    if "draft_id" in keep: keep["draft_id"]="set"
    print(f"| {now()} | {label} | {st} | {json.dumps(keep)[:230]} |")
print("| UTC | step | status | body (trimmed) |"); print("|---|---|---|---|")
a=Client(); a.guest(); show("guest A: prepare implicit EXACT text (task wording)", *a.request("POST","/api/webmcp/prepare",{"request_id":"r1","context":IMPLICIT_EXACT}))
b=Client(); b.guest(); show("guest B: prepare implicit FRESH text (nonce) — 1st time ever", *b.request("POST","/api/webmcp/prepare",{"request_id":"r1","context":IMPLICIT_FRESH}))
show("guest B: preview after refusal", *b.request("GET","/api/webmcp/preview"))
c=Client(); c.guest(); show("guest C: prepare implicit FRESH text again (does a refusal reserve?)", *c.request("POST","/api/webmcp/prepare",{"request_id":"r1","context":IMPLICIT_FRESH}))
d=Client(); d.guest(); show("guest D: prepare cue EXACT text (reserved by earlier P4 draft?)", *d.request("POST","/api/webmcp/prepare",{"request_id":"r1","context":CUE_EXACT}))
e=Client(); e.guest(); show("guest E: prepare cue FRESH text — 1st time ever (private draft, never shared)", *e.request("POST","/api/webmcp/prepare",{"request_id":"r1","context":CUE_FRESH}))
f=Client(); f.guest(); show("guest F: prepare cue FRESH text again (does a private draft reserve globally?)", *f.request("POST","/api/webmcp/prepare",{"request_id":"r1","context":CUE_FRESH}))
show("guest E: preview (own draft still there)", *e.request("GET","/api/webmcp/preview"))
