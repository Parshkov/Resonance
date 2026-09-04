"""P4: remote-MCP empty-draft refusal (stdlib; reuses abc_mcp_test.Identity -> ops.oauth_smoke.Smoke)."""
import json, sys, datetime, re
sys.path.insert(0, "/home/user/Resonance"); sys.path.insert(0, "/home/user/Resonance/submission/evidence")
from abc_mcp_test import Identity  # noqa

RES = "https://resonance-production-cfe3.up.railway.app/mcp"
IMPLICIT = ("Whenever the upstream degrades, thousands of clients notice timeouts at once and retry, "
            "and the whole tier ends up saturated. We think jittered backoff would help.")
CUE = ("A partial outage causes synchronized client retries. The retries cause request amplification, "
       "which leads to cascading saturation. Jittered backoff prevents the amplification.")
import os
NONCE = os.environ.get("NONCE", "")
IMPLICIT = IMPLICIT + (f" Ticket ref {NONCE}." if NONCE else "")
CUE = CUE + (f" Ticket ref {NONCE}." if NONCE else "")
rows = []; passed = 0; total = 0
def now(): return datetime.datetime.now(datetime.UTC).strftime("%H:%M:%SZ")
def ok(step, cond, note):
    global passed, total
    total += 1; passed += bool(cond)
    rows.append(f"| {now()} | {step} | {'PASS' if cond else 'FAIL'} | {note} |")
    return cond

ident = Identity("P4", RES)
ident.onboard()
ok("onboard guest via OAuth + initialize + whoami", bool(ident.user_id), f"user_id={ident.user_id[:10]}…")

status, _, resp = ident.rpc("tools/call", {"name": "resonance_prepare_thought", "arguments": {"context": IMPLICIT}})
result = resp.get("result") or {}
text = " ".join(c.get("text", "") for c in result.get("content", []) if isinstance(c, dict))
ok("prepare_thought(implicit prose) -> HTTP 200 JSON-RPC result", status == 200 and "result" in resp, f"http={status} rpc_error={'error' in resp}")
ok("result.isError is true", result.get("isError") is True, f"isError={result.get('isError')}")
ok("error text contains 'call again with `thought`'", "call again with `thought`" in text, f"text={text[:220]!r}")

mine = ident.call("resonance_my_thoughts", {})
sessions = mine.get("sessions", [])
disc = [s for s in sessions if s.get("discoverable") or s.get("shared")]
ok("my_thoughts -> no discoverable session after refusal", len(disc) == 0 and len(sessions) == 0,
   f"sessions={len(sessions)} discoverable={len(disc)} keys={sorted(mine.keys())}")

prep = ident.call("resonance_prepare_thought", {"context": CUE})
structure = prep.get("structure") or (prep.get("draft") or {}).get("structure") or {}
rels = structure.get("relations", []); nodes = structure.get("nodes", [])
n_rels = rels if isinstance(rels, int) else len(rels); n_nodes = nodes if isinstance(nodes, int) else len(nodes)
ok("prepare_thought(cue-explicit prose) succeeds", bool(prep), f"keys={sorted(prep.keys())}")
ok("structure.relations >= 1", n_rels >= 1, f"structure={json.dumps(structure)[:160]} nodes={n_nodes} relations={n_rels} input_kind={prep.get('input_kind')} discoverable={prep.get('discoverable')}")

out = ["# P4 — remote-MCP empty-draft refusal (HEAD 3c7dc80)", "",
       f"MCP: {RES} · run {datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds')}", "",
       f"NONCE={NONCE!r} (appended as a final sentence to keep the thought id fresh; see reservation probe)", "", "Bearer/refresh tokens, authorization codes and verifiers are never printed. user_id truncated.", "",
       "| UTC | step | result | note |", "|---|---|---|---|", *rows, "",
       f"implicit context (no cue words): {IMPLICIT!r}", "", f"cue-explicit context: {CUE!r}", "",
       f"**{passed}/{total} checks passed**", ""]
text_out = "\n".join(out)
tok = ident.smoke.access_token or ""
assert tok and tok not in text_out and (ident.smoke.refresh_token or "x") not in text_out
print(text_out)
sys.exit(0 if passed == total else 1)
