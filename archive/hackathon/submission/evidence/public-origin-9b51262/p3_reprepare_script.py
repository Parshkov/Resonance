#!/usr/bin/env python3
"""P3 (HEAD 9b51262): re-prepare regression on the public origin.

Fix under test: preparing the SAME raw `context` text again (same guest after
share+stop_sharing, and a second guest) must succeed with a fresh draft_id
instead of 409 "thought_id is already reserved".

stdlib only; reuses ops/oauth_smoke.Smoke via abc_mcp_test.Identity (OAuth guest
onboarding).  Output records statuses and draft_id equality only: no tokens,
codes, cookies, or confirmation tokens.
"""
import datetime, json, sys
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "submission" / "evidence"))
from abc_mcp_test import Identity  # noqa: E402  (inserts repo root on sys.path)

BASE = "https://resonance-production-cfe3.up.railway.app"
MCP = BASE + "/mcp"
CONTEXT = ("A partial outage causes synchronized client retries. The retries cause request "
           "amplification, which leads to cascading saturation. Jittered backoff prevents the amplification.")

SECRETS: set[str] = set()
rows: list[str] = []
passed = total = 0


def now() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%H:%M:%SZ")


def ok(step: str, status: str, expected: str, cond: bool, note: str = "") -> bool:
    global passed, total
    total += 1
    passed += bool(cond)
    rows.append(f"| {now()} | {step} | {status} | {expected} | {'PASS' if cond else 'FAIL'} | {note} |")
    return bool(cond)


def call(ident: Identity, name: str, arguments: dict):
    """Return (status_label, structuredContent-or-{}) without raising."""
    status, _, resp = ident.rpc("tools/call", {"name": name, "arguments": arguments})
    if status != 200:
        return f"http {status}", {}
    if "error" in resp:
        err = resp["error"]
        return f"rpc error {err.get('code')} {str(err.get('message', ''))[:120]!r}", {}
    result = resp.get("result") or {}
    if result.get("isError"):
        msg = " ".join(c.get("text", "") for c in result.get("content", []) if isinstance(c, dict))[:160]
        return f"tool isError {msg!r}", result.get("structuredContent") or {}
    return "ok", result.get("structuredContent") or {}


def relations_count(prep: dict) -> int:
    s = prep.get("structure") or {}
    rel = s.get("relations")
    if isinstance(rel, int):
        return rel
    if isinstance(rel, list):
        return len(rel)
    dna = (prep.get("will_become_discoverable") or {}).get("thought_dna") or {}
    return len(dna.get("relations") or [])


# ---- MCP path -------------------------------------------------------------
g1 = Identity("G1", MCP)
g1.onboard()
SECRETS.add(g1.smoke.access_token or "∅")
ok("G1 onboarded via OAuth (guest) + initialize + whoami", "ok", "user_id", bool(g1.user_id), f"user={g1.user_id}")

st, p1 = call(g1, "resonance_prepare_thought", {"context": CONTEXT})
SECRETS.add(p1.get("confirmation_token") or "∅")
r1 = relations_count(p1)
ok("G1 prepare #1 (raw context)", st, "ok, relations>=1", st == "ok" and r1 >= 1 and bool(p1.get("draft_id")),
   f"draft_id={p1.get('draft_id')} relations={r1} nodes={(p1.get('structure') or {}).get('nodes')} input_kind={p1.get('input_kind')} confirmation_token={'set' if p1.get('confirmation_token') else 'missing'}")

st, sh = call(g1, "resonance_share_thought", {"draft_id": p1.get("draft_id", ""), "confirmation_token": p1.get("confirmation_token", ""),
                                             "confirm": True, "request_id": "pulse5-g1-share"})
ok("G1 share (confirm=true + token)", st, "ok, discoverable=true", st == "ok" and sh.get("discoverable") is True and bool(sh.get("session_id")),
   f"session_id={sh.get('session_id')}")

st, stop = call(g1, "resonance_stop_sharing", {"session_id": sh.get("session_id", ""), "confirm": True})
ok("G1 stop_sharing (confirm=true)", st, "ok", st == "ok", f"keys={sorted(stop.keys())[:8]}")

st, p2 = call(g1, "resonance_prepare_thought", {"context": CONTEXT})
SECRETS.add(p2.get("confirmation_token") or "∅")
r2 = relations_count(p2)
ok("G1 prepare #2 (SAME exact context, after stop_sharing) — regression", st, "ok (previously 409 thought_id already reserved)",
   st == "ok" and r2 >= 1 and bool(p2.get("draft_id")), f"draft_id={p2.get('draft_id')} relations={r2}")
ok("G1 draft_id #2 != draft_id #1", "-", "different", bool(p1.get("draft_id")) and bool(p2.get("draft_id")) and p1.get("draft_id") != p2.get("draft_id"),
   f"{p1.get('draft_id')} vs {p2.get('draft_id')}")

g2 = Identity("G2", MCP)
g2.onboard()
SECRETS.add(g2.smoke.access_token or "∅")
ok("G2 onboarded via OAuth (guest), distinct user", "ok", "user_id != G1", bool(g2.user_id) and g2.user_id != g1.user_id, f"user={g2.user_id}")
st, p3 = call(g2, "resonance_prepare_thought", {"context": CONTEXT})
SECRETS.add(p3.get("confirmation_token") or "∅")
r3 = relations_count(p3)
ok("G2 prepare (SAME exact context) — regression", st, "ok", st == "ok" and r3 >= 1 and bool(p3.get("draft_id")),
   f"draft_id={p3.get('draft_id')} relations={r3}")
ok("G2 draft_id differs from G1's two drafts", "-", "different", bool(p3.get("draft_id")) and p3.get("draft_id") not in {p1.get("draft_id"), p2.get("draft_id")},
   f"{p3.get('draft_id')}")


# ---- browser path (cookie + CSRF) -------------------------------------------
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
            try:
                return e.code, json.loads(e.read().decode() or "{}")
            except json.JSONDecodeError:
                return e.code, {}

    def guest(self):
        st, p = self.request("POST", "/api/product/guest", {})
        self.csrf = p.get("csrf_token"); SECRETS.add(self.csrf or "∅")
        SECRETS.add(p.get("recovery_secret") or "∅")
        return st, p


c = Client()
st, _ = c.guest()
ok("browser: POST /api/product/guest", str(st), "200 + cookie + csrf", st == 200 and bool(c.cookie) and bool(c.csrf),
   f"cookie={'set' if c.cookie else 'missing'} csrf={'set' if c.csrf else 'missing'}")
st, bp = c.request("POST", "/api/webmcp/prepare", {"request_id": "pulse5-browser-prep-1", "context": CONTEXT})
ok("browser: POST /api/webmcp/prepare (SAME exact context)", str(st), "200",
   st == 200 and bool(bp.get("draft_id")) and bp.get("discoverable") is False,
   f"draft_id={bp.get('draft_id')} input_kind={bp.get('input_kind')} discoverable={bp.get('discoverable')} error={bp.get('error')}")
ok("browser draft_id differs from the three MCP drafts", "-", "different",
   bool(bp.get("draft_id")) and bp.get("draft_id") not in {p1.get("draft_id"), p2.get("draft_id"), p3.get("draft_id")}, "")
rows.append(f"| {now()} | browser: POST /api/webmcp/consent shared=false | skipped | n/a | n/a | never shared on this path; not needed |")

out = ["# P3 — re-prepare regression (same raw `context` twice) on the public origin (HEAD 9b51262)", "",
       f"Origin: {BASE} · MCP: {MCP} · run {datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds')}", "",
       "Context text: the exact three-sentence retry-storm paragraph specified for this pulse (no nonce). "
       "Access/refresh tokens, authorization codes, confirmation tokens, the resonance_token cookie, csrf_token and recovery_secret are never printed.", "",
       "| UTC | step | status | expected | result | note |", "|---|---|---|---|---|---|", *rows, "",
       "## draft_id equality", "", "| pair | equal? |", "|---|---|",
       f"| G1 #1 vs G1 #2 | {p1.get('draft_id') == p2.get('draft_id')} |",
       f"| G1 #1 vs G2 | {p1.get('draft_id') == p3.get('draft_id')} |",
       f"| G1 #2 vs G2 | {p2.get('draft_id') == p3.get('draft_id')} |",
       f"| MCP drafts vs browser | {bp.get('draft_id') in {p1.get('draft_id'), p2.get('draft_id'), p3.get('draft_id')}} |", "",
       f"**{passed}/{total} checks passed**", ""]
text = "\n".join(out)
for s in SECRETS:
    assert s == "∅" or s not in text, "secret leaked into evidence"
print(text)
sys.exit(0 if passed == total else 1)
