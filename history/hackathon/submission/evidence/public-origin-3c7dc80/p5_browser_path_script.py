"""P5: browser-path (cookie + CSRF) prepare -> preview -> share -> context -> discover -> consent; plus implicit-prose refusal."""
import json, sys, datetime
from http.cookies import SimpleCookie
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "https://resonance-production-cfe3.up.railway.app"
THOUGHT = {"topic": "Panic buying after a shortage rumour", "domain": "consumer-economics",
           "nodes": [{"id": "b0", "label": "supply shortage rumour", "role": "problem"},
                     {"id": "b1", "label": "synchronized bulk purchases", "role": "mechanism"},
                     {"id": "b2", "label": "demand amplification", "role": "state"},
                     {"id": "b3", "label": "empty shelves", "role": "outcome"},
                     {"id": "b5", "label": "staggered restocking", "role": "method"}],
           "relations": [{"source": "b0", "target": "b1", "type": "causes"},
                         {"source": "b1", "target": "b2", "type": "causes"},
                         {"source": "b2", "target": "b3", "type": "causes"},
                         {"source": "b3", "target": "b1", "type": "causes"},
                         {"source": "b5", "target": "b2", "type": "prevents"}]}
IMPLICIT = ("Whenever the upstream degrades, thousands of clients notice timeouts at once and retry, "
            "and the whole tier ends up saturated. We think jittered backoff would help.")
SECRETS = set()
import os
NONCE = os.environ.get("NONCE", "")
IMPLICIT = IMPLICIT + (f" Ticket ref {NONCE}." if NONCE else "")

class Client:
    def __init__(self):
        self.cookie = None; self.csrf = None
    def request(self, method, path, body=None):
        headers = {"Content-Type": "application/json", "Origin": BASE}
        if self.cookie: headers["Cookie"] = self.cookie
        if self.csrf: headers["X-Resonance-CSRF"] = self.csrf
        data = json.dumps(body).encode() if body is not None else None
        req = Request(BASE + path, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=30) as r:
                sc = r.headers.get("Set-Cookie")
                if sc:
                    m = SimpleCookie(sc).get("resonance_token")
                    if m is not None:
                        self.cookie = f"resonance_token={m.value}"; SECRETS.add(m.value)
                return r.status, json.loads(r.read().decode() or "{}")
        except HTTPError as e:
            return e.code, json.loads(e.read().decode() or "{}")
    def guest(self):
        st, p = self.request("POST", "/api/product/guest", {})
        self.csrf = p.get("csrf_token"); SECRETS.add(self.csrf or "∅")
        return st, p

rows = []; passed = 0; total = 0
def now(): return datetime.datetime.now(datetime.UTC).strftime("%H:%M:%SZ")
def ok(step, status, expected, cond, note):
    global passed, total
    total += 1; passed += bool(cond)
    rows.append(f"| {now()} | {step} | {status} | {expected} | {'PASS' if cond else 'FAIL'} | {note} |")

c = Client()
st, g = c.guest()
ok("POST /api/product/guest", st, 200, st == 200 and c.cookie and c.csrf, f"cookie={'set' if c.cookie else 'missing'} csrf={'set' if c.csrf else 'missing'}")
st, prep = c.request("POST", "/api/webmcp/prepare", {"request_id": "pulse4-prep-1", "thought": THOUGHT})
ok("POST /api/webmcp/prepare (structured thought, 5 nodes)", st, 200, st == 200 and prep.get("input_kind") == "agent_structured" and prep.get("discoverable") is False,
   f"input_kind={prep.get('input_kind')} discoverable={prep.get('discoverable')} source_retention={prep.get('source_retention')}")
st, prev = c.request("GET", "/api/webmcp/preview")
wb = prev.get("will_become_discoverable", {})
labels = {n.get("label") for n in wb.get("thought", {}).get("nodes", [])}
ctoken = prev.get("confirmation_token"); SECRETS.add(ctoken or "∅")
ok("GET /api/webmcp/preview", st, 200, st == 200 and labels == {n["label"] for n in THOUGHT["nodes"]} and ctoken,
   f"labels_found={len(labels & {n['label'] for n in THOUGHT['nodes']})}/5 topic={wb.get('presentation', {}).get('topic')!r} confirmation_token={'set' if ctoken else 'missing'}")
st, sh = c.request("POST", "/api/webmcp/share", {"request_id": "pulse4-share-1", "confirm": True, "confirmation_token": ctoken})
ok("POST /api/webmcp/share (confirm=true)", st, 200, st == 200 and sh.get("shared") and sh.get("discoverable"), f"shared={sh.get('shared')} discoverable={sh.get('discoverable')}")
st, live = c.request("GET", "/api/context?source=live")
live_labels = {n.get("label") for n in live.get("active_thought", {}).get("nodes", [])}
ok("GET /api/context?source=live -> own thought", st, 200,
   st == 200 and live_labels == {n["label"] for n in THOUGHT["nodes"]} and live.get("presentation", {}).get("topic") == THOUGHT["topic"],
   f"topic={live.get('presentation', {}).get('topic')!r} own_labels={len(live_labels & {n['label'] for n in THOUGHT['nodes']})}/5 thought_id={live.get('active_thought', {}).get('thought_id')} shared_with_resonance={live.get('consent', {}).get('shared_with_resonance')}")
st, rep = c.request("GET", "/api/context?source=replay")
ok("GET /api/context?source=replay -> fixture thought", st, 200, st == 200 and rep.get("active_thought", {}).get("thought_id") == "thought-aria-plasma-lens",
   f"thought_id={rep.get('active_thought', {}).get('thought_id')}")
st, disc = c.request("GET", "/api/discover?source=live")
matches = disc.get("matches", [])
first3 = [{"mode_classification": m.get("mode_classification"), "scores": m.get("scores")} for m in matches[:3]]
ok("GET /api/discover?source=live", st, 200, st == 200 and len(matches) > 0, f"matches={len(matches)} contract_version={disc.get('contract_version')}")
st, cons = c.request("POST", "/api/webmcp/consent", {"request_id": "pulse4-consent-1", "shared": False})
ok("POST /api/webmcp/consent (shared=false)", st, 200, st == 200 and cons.get("revoked") is True and cons.get("discoverable") is False,
   f"revoked={cons.get('revoked')} shared={cons.get('shared')} discoverable={cons.get('discoverable')}")

c2 = Client(); st, _ = c2.guest()
ok("POST /api/product/guest (second guest)", st, 200, st == 200, "fresh identity for the refusal check")
st, bad = c2.request("POST", "/api/webmcp/prepare", {"request_id": "pulse4-implicit-1", "context": IMPLICIT})
ok("POST /api/webmcp/prepare (implicit prose context)", st, 400, st == 400 and bad.get("error") == "validation_failed" and "thought" in (bad.get("message") or ""),
   f"error={bad.get('error')} message={(bad.get('message') or '')[:200]!r}")
st, pv = c2.request("GET", "/api/webmcp/preview")
ok("GET /api/webmcp/preview (no draft left)", st, 409, st == 409, f"error={pv.get('error')}")

out = ["# P5 — browser-path (cookie + CSRF, stdlib) on the public origin (HEAD 3c7dc80)", "",
       f"Origin: {BASE} · run {datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds')}", "",
       f"NONCE={NONCE!r} (appended to the implicit prose to keep the thought id fresh; see reservation probe)", "", "resonance_token cookie, csrf_token and confirmation_token values are redacted (only set/missing is recorded).", "",
       "| UTC | step | status | expected | result | note |", "|---|---|---|---|---|---|", *rows, "",
       "## /api/discover?source=live — first three matches", "", "```json", json.dumps(first3, indent=1), "```", "",
       f"top match keys: {sorted(matches[0].keys()) if matches else []}", "",
       f"**{passed}/{total} checks passed**", ""]
text = "\n".join(out)
for s in SECRETS:
    assert s == "∅" or s not in text, "secret leaked into evidence"
print(text)
sys.exit(0 if passed == total else 1)
