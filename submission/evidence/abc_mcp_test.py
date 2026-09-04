#!/usr/bin/env python3
"""R17 acceptance: REAL multi-user A/B/C structural test over the canonical
remote MCP endpoint, using ONLY the public `/mcp` URL + standard OAuth onboarding
(three independent pseudonymous guest identities; no key, no bearer copy, no
capability URL).

    python3 submission/evidence/abc_mcp_test.py https://resonance-production-cfe3.up.railway.app/mcp \
        --out submission/evidence/public-origin/abc.json

A = retry storm / outage feedback loop            (distributed systems)
B = panic buying / shortage feedback loop         (consumer economics)  -> lexically different, structurally analogous to A
C = retry/outage observability, no feedback loop  (shares A's vocabulary, weaker structure)

Flow: A,B,C each onboard via OAuth -> prepare (structured Thought DNA) -> share (explicit
confirm + confirmation_token); B discover -> expect A above C; B explain_match(A);
B request_intro(A); A list_intros -> accept; A send_message; B read_messages;
A stop_sharing; B discover again -> A absent. Also negative: B cannot explain A's match
through a result_id it does not own... (subject isolation), unknown Mcp-Session-Id -> 404.

Output is privacy-safe: pseudonymous ids, session/result ids, scores, relation mappings,
state transitions. No tokens, no codes, no raw text beyond short noun-phrase labels.
stdlib only; reuses ops/oauth_smoke.Smoke for discovery-driven OAuth onboarding.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ops.oauth_smoke import REDIRECT_URI, Smoke  # noqa: E402

THOUGHTS = {
    "A": {
        "topic": "Retry storm after a partial outage",
        "domain": "distributed-systems",
        "nodes": [
            {"id": "a0", "label": "partial upstream outage", "role": "problem"},
            {"id": "a1", "label": "synchronized client retries", "role": "mechanism"},
            {"id": "a2", "label": "request amplification", "role": "state"},
            {"id": "a3", "label": "cascading saturation", "role": "outcome"},
            {"id": "a4", "label": "fixed retry budget", "role": "constraint"},
            {"id": "a5", "label": "jittered exponential backoff", "role": "method"},
        ],
        "relations": [
            {"source": "a0", "target": "a1", "type": "causes"},
            {"source": "a1", "target": "a2", "type": "causes"},
            {"source": "a2", "target": "a3", "type": "causes"},
            {"source": "a3", "target": "a1", "type": "causes"},
            {"source": "a5", "target": "a2", "type": "prevents"},
            {"source": "a4", "target": "a1", "type": "constrains"},
        ],
    },
    "B": {
        "topic": "Panic buying after a shortage rumour",
        "domain": "consumer-economics",
        "nodes": [
            {"id": "b0", "label": "supply shortage rumour", "role": "problem"},
            {"id": "b1", "label": "synchronized bulk purchases", "role": "mechanism"},
            {"id": "b2", "label": "demand amplification", "role": "state"},
            {"id": "b3", "label": "empty shelves", "role": "outcome"},
            {"id": "b4", "label": "per-customer purchase cap", "role": "constraint"},
            {"id": "b5", "label": "staggered restocking", "role": "method"},
        ],
        "relations": [
            {"source": "b0", "target": "b1", "type": "causes"},
            {"source": "b1", "target": "b2", "type": "causes"},
            {"source": "b2", "target": "b3", "type": "causes"},
            {"source": "b3", "target": "b1", "type": "causes"},
            {"source": "b5", "target": "b2", "type": "prevents"},
            {"source": "b4", "target": "b1", "type": "constrains"},
        ],
    },
    "C": {
        "topic": "Retry and outage observability",
        "domain": "distributed-systems",
        "nodes": [
            {"id": "c0", "label": "partial upstream outage", "role": "problem"},
            {"id": "c1", "label": "client retries", "role": "mechanism"},
            {"id": "c2", "label": "retry metrics dashboard", "role": "resource"},
            {"id": "c3", "label": "outage timeline report", "role": "evidence"},
            {"id": "c4", "label": "alert on error budget", "role": "method"},
        ],
        "relations": [
            {"source": "c0", "target": "c1", "type": "causes"},
            {"source": "c2", "target": "c3", "type": "supports"},
            {"source": "c4", "target": "c3", "type": "requires"},
        ],
    },
}


class Identity:
    """One independent user: its own OAuth onboarding, bearer and MCP session."""

    def __init__(self, name: str, resource: str) -> None:
        self.name = name
        self.smoke = Smoke(resource, auto_consent=True, verbose=False)
        self.smoke.ok = lambda step, cond, detail="": bool(cond)  # quiet
        self.resource = resource
        self.session_id: str | None = None
        self.user_id: str | None = None
        self._mid = 10

    def onboard(self) -> None:
        s = self.smoke
        status, headers, _ = s._rpc("ping", mid=1, bearer=None)
        assert status == 401, f"{self.name}: unauth /mcp status {status}"
        import re
        m = re.search(r'resource_metadata="([^"]+)"', headers.get("WWW-Authenticate", ""))
        assert m, f"{self.name}: no resource_metadata in challenge"
        _, _, prm = s._json(m.group(1))
        issuer = prm["authorization_servers"][0].rstrip("/")
        _, _, asm = s._json(f"{issuer}/.well-known/oauth-authorization-server")
        s.meta = asm
        _, _, client = s._json(asm["registration_endpoint"], method="POST",
                               headers={"Content-Type": "application/json"},
                               data=json.dumps({"client_name": f"resonance-abc-{self.name}",
                                                "redirect_uris": [REDIRECT_URI],
                                                "grant_types": ["authorization_code", "refresh_token"],
                                                "response_types": ["code"],
                                                "token_endpoint_auth_method": "none"}).encode())
        s.client_id = client["client_id"]
        code = s._authorize(quiet=True)
        assert code, f"{self.name}: authorize/consent produced no code"
        status, _, tok = s._token({"grant_type": "authorization_code", "code": code,
                                   "code_verifier": s._verifier, "redirect_uri": REDIRECT_URI,
                                   "client_id": s.client_id, "resource": self.resource})
        assert status == 200 and tok.get("access_token"), f"{self.name}: token exchange {status} {tok.get('error')}"
        s.access_token = tok["access_token"]
        s.refresh_token = tok.get("refresh_token")
        status, headers, init = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                                        "clientInfo": {"name": "abc-test", "version": "0"}})
        assert status == 200 and "result" in init, f"{self.name}: initialize {status}"
        self.session_id = headers.get("Mcp-Session-Id") or headers.get("mcp-session-id")
        who = self.call("resonance_whoami", {})
        self.user_id = who["user_id"]

    def rpc(self, method: str, params=None):
        self._mid += 1
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                   "Authorization": f"Bearer {self.smoke.access_token}"}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        body = json.dumps({"jsonrpc": "2.0", "id": self._mid, "method": method, "params": params or {}}).encode()
        return self.smoke._json(self.resource, method="POST", data=body, headers=headers)

    def call(self, name: str, arguments: dict):
        status, _, resp = self.rpc("tools/call", {"name": name, "arguments": arguments})
        if status != 200 or "error" in resp:
            raise RuntimeError(f"{self.name}: {name} -> HTTP {status} {json.dumps(resp)[:300]}")
        result = resp["result"]
        if result.get("isError"):
            raise RuntimeError(f"{self.name}: {name} tool error {json.dumps(result)[:300]}")
        return result.get("structuredContent") or {}

    def call_expect_error(self, name: str, arguments: dict):
        status, _, resp = self.rpc("tools/call", {"name": name, "arguments": arguments})
        if status != 200:
            return f"http {status}"
        if "error" in resp:
            return f"rpc {resp['error'].get('code')}"
        if (resp.get("result") or {}).get("isError"):
            return "tool isError"
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("resource")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    resource = args.resource.rstrip("/")
    ev: dict = {"resource": resource, "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "steps": []}
    checks: list[tuple[str, bool, str]] = []

    def ok(step: str, cond: bool, detail: str = "") -> bool:
        checks.append((step, bool(cond), detail))
        print(f"[{'PASS' if cond else 'FAIL'}] {step}" + (f" — {detail}" if detail else ""))
        return bool(cond)

    ids = {n: Identity(n, resource) for n in ("A", "B", "C")}
    for n, ident in ids.items():
        ident.onboard()
        ok(f"{n} onboarded via OAuth (guest) + MCP initialize + whoami", bool(ident.user_id),
           f"user={ident.user_id} transport={'stateful (Mcp-Session-Id issued)' if ident.session_id else 'stateless (no Mcp-Session-Id; spec-permitted)'}")
    ok("three independent identities", len({i.user_id for i in ids.values()}) == 3)
    ev["identities"] = {n: {"user_id": i.user_id} for n, i in ids.items()}

    shared: dict[str, dict] = {}
    for n, ident in ids.items():
        prep = ident.call("resonance_prepare_thought", {"thought": THOUGHTS[n]})
        ok(f"{n} prepare -> private draft (discoverable=false)", prep.get("discoverable") is False and prep.get("confirmation_token"),
           f"draft={prep.get('draft_id')} input_kind={prep.get('input_kind')} retention={prep.get('source_retention')}")
        # nothing discoverable before confirm: the owner's own list shows no shared session
        mine = ident.call("resonance_my_thoughts", {})
        pre_shared = [s for s in mine.get("sessions", []) if s.get("shared") or s.get("discoverable")]
        ok(f"{n} nothing discoverable before explicit confirm", not pre_shared, f"shared_before={len(pre_shared)}")
        # share without confirm must fail
        err = ident.call_expect_error("resonance_share_thought", {"draft_id": prep["draft_id"],
                                                                  "confirmation_token": prep["confirmation_token"],
                                                                  "confirm": False, "request_id": f"abc-{n}-noconfirm"})
        ok(f"{n} share with confirm=false rejected", err is not None, str(err))
        sh = ident.call("resonance_share_thought", {"draft_id": prep["draft_id"],
                                                    "confirmation_token": prep["confirmation_token"],
                                                    "confirm": True, "request_id": f"abc-{n}-share"})
        ok(f"{n} explicit share -> discoverable=true", sh.get("discoverable") is True and sh.get("session_id"),
           f"session={sh.get('session_id')}")
        shared[n] = {"draft_id": prep["draft_id"], "session_id": sh.get("session_id"),
                     "preview_nodes": len(((prep.get("will_become_discoverable") or {}).get("thought_dna") or {}).get("nodes", [])),
                     "preview_relations": len(((prep.get("will_become_discoverable") or {}).get("thought_dna") or {}).get("relations", []))}
    ev["shared"] = shared

    # B discovers
    b = ids["B"]
    disc = b.call("resonance_discover", {"session_id": shared["B"]["session_id"], "k": 15})
    matches = disc.get("matches_in_backend_order", [])
    by_sid = {m.get("session_id"): (rank, m) for rank, m in enumerate(matches)}
    a_hit = by_sid.get(shared["A"]["session_id"])
    c_hit = by_sid.get(shared["C"]["session_id"])

    def score_of(m):
        return (m.get("score") if m.get("score") is not None else (m.get("scores") or {}).get("structural")
                or (m.get("evidence") or {}).get("structural_score"))

    ok("B discover returns result_id from live source", bool(disc.get("result_id")) and disc.get("source") in ("live", None),
       f"result_id={disc.get('result_id')} source={disc.get('source')} matches={len(matches)}")
    ok("A (retry storm) found by B (panic buying)", a_hit is not None,
       f"rank={a_hit[0] if a_hit else None} score={score_of(a_hit[1]) if a_hit else None} mode={a_hit[1].get('mode') if a_hit else None}")
    ok("A ranks above C (structure beats shared vocabulary)",
       a_hit is not None and (c_hit is None or a_hit[0] < c_hit[0]),
       f"rank_A={a_hit[0] if a_hit else None} rank_C={c_hit[0] if c_hit else 'absent'} "
       f"score_C={score_of(c_hit[1]) if c_hit else None}")
    ev["discover_B"] = {"result_id": disc.get("result_id"), "source": disc.get("source"),
                        "matches": [{"rank": r, "session_id": m.get("session_id"), "mode": m.get("mode"),
                                     "score": score_of(m), "scores": m.get("scores"),
                                     "is_A": m.get("session_id") == shared["A"]["session_id"],
                                     "is_C": m.get("session_id") == shared["C"]["session_id"]}
                                    for r, m in enumerate(matches)],
                        "rejected_count": len(disc.get("rejected", []))}

    if a_hit:
        expl = b.call("resonance_explain_match", {"result_id": disc["result_id"], "session_id": shared["A"]["session_id"]})
        ev["explain_A"] = {k: expl.get(k) for k in ("source", "result_id", "match") if k in expl}
        ok("B explain_match(A) returns structural evidence", bool(expl), f"keys={sorted(expl.keys())[:12]}")
        # subject isolation: C cannot use B's result_id
        err = ids["C"].call_expect_error("resonance_explain_match", {"result_id": disc["result_id"], "session_id": shared["A"]["session_id"]})
        ok("C cannot read B's discovery result (result_id subject-bound)", err is not None, str(err))

    # intro flow
    intro = b.call("resonance_request_intro", {"from_session_id": shared["B"]["session_id"],
                                                "target_session_id": shared["A"]["session_id"],
                                                "message": "Your loop looks like mine. Talk?",
                                                "confirm": True, "request_id": "abc-B-intro"})
    intro_id = intro.get("intro_id") or (intro.get("request") or {}).get("intro_id") or intro.get("id")
    ok("B requests intro to A", bool(intro_id), f"intro={intro_id} state={intro.get('state') or (intro.get('request') or {}).get('state')}")
    # duplicate retry with same request_id must not create a second intro
    intro2 = b.call("resonance_request_intro", {"from_session_id": shared["B"]["session_id"],
                                                 "target_session_id": shared["A"]["session_id"],
                                                 "message": "Your loop looks like mine. Talk?",
                                                 "confirm": True, "request_id": "abc-B-intro"})
    intro_id2 = intro2.get("intro_id") or (intro2.get("request") or {}).get("intro_id") or intro2.get("id")
    ok("intro retry with same request_id is idempotent", intro_id2 == intro_id, f"{intro_id2} == {intro_id}")
    a = ids["A"]
    lst = a.call("resonance_list_intros", {})
    incoming = lst.get("incoming") or lst.get("received") or []
    inc = next((r for r in incoming if (r.get("intro_id") or r.get("id")) == intro_id), None)
    ok("A sees the incoming intro", inc is not None, f"incoming={len(incoming)}")
    resp = a.call("resonance_respond_intro", {"intro_id": intro_id, "accept": True, "confirm": True, "request_id": "abc-A-accept"})
    channel = resp.get("channel_id") or (resp.get("request") or {}).get("channel_id") or (resp.get("channel") or {}).get("channel_id")
    if not channel:
        lst = a.call("resonance_list_intros", {})
        for r in (lst.get("incoming") or []) + (lst.get("outgoing") or []):
            if (r.get("intro_id") or r.get("id")) == intro_id and r.get("channel_id"):
                channel = r["channel_id"]
    ok("A accepts -> channel opened", bool(channel), f"channel={channel} state={resp.get('state')}")
    msg = a.call("resonance_send_message", {"channel_id": channel, "body": "Yes — same shape, different world.",
                                            "confirm": True, "request_id": "abc-A-msg1"})
    ok("A sends a relay message", bool(msg), f"message={msg.get('message_id') or (msg.get('message') or {}).get('message_id')}")
    inbox = b.call("resonance_read_messages", {"channel_id": channel})
    msgs = inbox.get("messages") or []
    ok("B reads A's message", any("same shape" in (m.get("body") or "") for m in msgs), f"count={len(msgs)}")
    # C is not a party to the channel
    err = ids["C"].call_expect_error("resonance_read_messages", {"channel_id": channel})
    ok("C cannot read the A<->B channel", err is not None, str(err))
    ev["intro"] = {"intro_id": intro_id, "channel_id": channel, "accepted": bool(channel), "messages": len(msgs)}

    # revoke
    rv = a.call("resonance_stop_sharing", {"session_id": shared["A"]["session_id"], "confirm": True})
    ok("A stop_sharing -> revoked", rv.get("revoked") is True and rv.get("discoverable") is False)
    disc2 = b.call("resonance_discover", {"session_id": shared["B"]["session_id"], "k": 15})
    sids2 = [m.get("session_id") for m in disc2.get("matches_in_backend_order", [])]
    ok("fresh discovery: revoked A is absent immediately", shared["A"]["session_id"] not in sids2,
       f"result_id={disc2.get('result_id')} matches={len(sids2)}")
    err = b.call_expect_error("resonance_explain_match", {"result_id": disc["result_id"], "session_id": shared["A"]["session_id"]})
    ok("old result_id no longer serves revoked A's evidence", err is not None, str(err))
    ev["revoke"] = {"A_session": shared["A"]["session_id"], "second_result_id": disc2.get("result_id"),
                    "A_absent": shared["A"]["session_id"] not in sids2}

    # stale MCP session
    stale = Identity("B-stale", resource)
    stale.smoke.access_token = b.smoke.access_token
    stale.session_id = "ses-does-not-exist-0000"
    status, _, resp = stale.rpc("tools/list")
    if b.session_id:
        ok("unknown Mcp-Session-Id -> HTTP 404 (client re-initializes)", status == 404, f"status={status}")
    else:
        ok("stateless transport: a stale Mcp-Session-Id is ignored, bearer still authoritative (restart-safe)",
           status == 200 and "result" in resp, f"status={status}")
    # restart/reconnect equivalence: a brand-new MCP client session with the same bearer sees the same account
    fresh = Identity("B-fresh", resource); fresh.smoke.access_token = b.smoke.access_token
    st, hd, init = fresh.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "abc-reconnect", "version": "0"}})
    fresh.session_id = hd.get("Mcp-Session-Id") or hd.get("mcp-session-id")
    who2 = fresh.call("resonance_whoami", {})
    ok("reconnect: fresh initialize with the same bearer maps to the same account", who2.get("user_id") == b.user_id)
    # token in query string must not authenticate
    status, _, resp = Smoke(resource, auto_consent=True, verbose=False)._json(
        resource + "?" + urlencode({"access_token": b.smoke.access_token}), method="POST",
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode(),
        headers={"Content-Type": "application/json"})
    ok("access_token in query string does NOT authenticate", status == 401, f"status={status}")
    # revoke B's access token via RFC 7009, then bearer must fail
    _, _, asm = b.smoke._json(resource.rsplit("/", 1)[0] + "/.well-known/oauth-authorization-server")
    rev = asm.get("revocation_endpoint")
    if rev:
        st, _, _ = b.smoke._json(rev, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"},
                                 data=urlencode({"token": b.smoke.access_token, "token_type_hint": "access_token",
                                                 "client_id": b.smoke.client_id}).encode())
        st2, _, _ = b.rpc("tools/list")
        ok("revoked access token stops working on /mcp", st == 200 and st2 == 401, f"revoke={st} then /mcp={st2}")

    ev["checks"] = [{"step": s, "ok": o, "detail": d} for s, o, d in checks]
    ev["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    failed = [c for c in checks if not c[1]]
    ev["summary"] = f"{len(checks) - len(failed)}/{len(checks)} checks passed"
    print("\n" + ev["summary"] + (f"; FAILED: {', '.join(c[0] for c in failed)}" if failed else ""))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(ev, indent=2)
        for secret in {i.smoke.access_token for i in ids.values()} | {i.smoke.refresh_token for i in ids.values()}:
            if secret:
                assert secret not in text, "token leaked into evidence"
        Path(args.out).write_text(text + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
