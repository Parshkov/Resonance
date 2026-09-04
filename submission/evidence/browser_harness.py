#!/usr/bin/env python3
"""Browser evidence for the WebMCP page (supporting evidence, labelled honestly).

Loads the competition page in headless Chromium via Playwright, records whether a
NATIVE `document.modelContext` exists, and — when it does not — installs a minimal
modelContext shim BEFORE page scripts so the page's own `registerWebMCP()` registers
its six tools through the standard `registerTool(tool, {signal})` call. The tools'
`execute` functions are then invoked exactly as an agent-capable browser would, and
the visible page state (status pill, header consent, cards) is captured after each
step with screenshots.

This is NOT native WebMCP discovery; it proves the page-side registration and the
tool contract end to end against the live product state on the origin under test.

    python3 submission/evidence/browser_harness.py http://127.0.0.1:8788 --out submission/evidence/local-postgres
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

SHIM = """
(() => {
  const tools = [];
  const mc = { registerTool(tool, opts) { tools.push(tool); return Promise.resolve(); },
               unregisterTool(name) { const i = tools.findIndex(t => t.name === name); if (i >= 0) tools.splice(i, 1); } };
  Object.defineProperty(mc, '__tools', { get: () => tools });
  window.__harnessModelContext = mc;
  if (!document.modelContext) Object.defineProperty(document, 'modelContext', { value: mc, configurable: true });
})();
"""

CALL = """
async ([name, args]) => {
  const mc = document.modelContext;
  const tool = mc.__tools.find(t => t.name === name);
  if (!tool) throw new Error('tool not registered: ' + name);
  try {
    const out = await tool.execute(args, {signal: new AbortController().signal});
    return JSON.parse(JSON.stringify(out));
  } catch (e) {
    return {isError: true, error: e.code || 'error', status: e.status || null, message: String(e.message || e)};
  }
}
"""


def text(page, sel):
    try:
        return page.locator(sel).first.inner_text(timeout=1500)
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("origin")
    ap.add_argument("--out", required=True)
    ap.add_argument("--exe", default=os.environ.get("CHROME_EXE"))
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    ev = {"origin": args.origin, "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "steps": []}
    checks = []

    def ok(step, cond, detail=""):
        checks.append({"step": step, "ok": bool(cond), "detail": detail})
        print(f"[{'PASS' if cond else 'FAIL'}] {step}" + (f" — {detail}" if detail else ""))
        return bool(cond)

    with sync_playwright() as p:
        launch = {"args": ["--enable-features=WebMCP,WebMCPTesting"]}
        if args.exe:
            launch["executable_path"] = args.exe
        # 1) native probe: no shim
        b = p.chromium.launch(**launch)
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        console = []
        pg.on("console", lambda m: console.append(f"{m.type}: {m.text}"))
        pg.goto(args.origin + "/", wait_until="networkidle", timeout=60000)
        native = pg.evaluate("typeof document.modelContext")
        native_nav = pg.evaluate("typeof navigator.modelContext")
        ev["browser"] = {"version": b.version, "native_document_modelContext": native,
                         "native_navigator_modelContext": native_nav}
        ok("page loads (title + app shell)", pg.title() and pg.locator("#app-shell").count() == 1, f"title={pg.title()!r}")
        ok("NATIVE document.modelContext present", native != "undefined",
           f"typeof document.modelContext={native}; navigator.modelContext={native_nav} in Chromium {b.version} (absent = expected in stock Chromium; native evidence needs a WebMCP-enabled Chrome)")
        ev["native_status_pill"] = text(pg, "#webmcp-status")
        ev["native_contract"] = pg.evaluate("window.__resonanceWebMCP || null")
        ok("page exposes WebMCP contract + six tool names", bool(ev["native_contract"]) and len(ev["native_contract"].get("toolNames", [])) == 6,
           json.dumps(ev["native_contract"]))
        pg.screenshot(path=str(out / "browser_01_native_load.png"), full_page=False)
        ev["console_native"] = console[:40]
        b.close()

        # 2) harness run: shim installed before page scripts
        b = p.chromium.launch(**launch)
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_init_script(SHIM)
        pg = ctx.new_page()
        console = []
        pg.on("console", lambda m: console.append(f"{m.type}: {m.text}"))
        pg.goto(args.origin + "/", wait_until="networkidle", timeout=60000)
        pg.wait_for_timeout(1500)
        names = pg.evaluate("document.modelContext.__tools.map(t => t.name)")
        six = ["resonance_prepare_thought", "resonance_get_share_preview", "resonance_share_prepared_thought",
               "resonance_discover", "resonance_get_match", "resonance_update_consent"]
        ok("HARNESS: page registered its tools via document.modelContext.registerTool (six R10 tools + collaboration/workspace tools)",
           all(n in names for n in six), f"{len(names)} tools: " + ", ".join(names))
        ok("HARNESS: status pill reports registration", (text(pg, "#webmcp-status") or "").startswith("WebMCP ·"), text(pg, "#webmcp-status"))
        ev["harness_tools"] = names
        ev["header_before"] = text(pg, "#header-consent")

        def call(name, a):
            r = pg.evaluate(CALL, [name, a])
            sc = r.get("structuredContent") if isinstance(r, dict) else None
            return r, (sc or r)

        # A fresh visitor has nothing shared: discovery must fail closed with a
        # mapped product state (409 share_required), never a 500.
        pre = pg.evaluate("""async () => { const r = await fetch('/api/webmcp/discover?source=replay', {credentials:'same-origin'}); return {status: r.status, body: await r.text()}; }""")
        ok("nothing discoverable before share: discover(replay) fails closed with 409 share_required",
           pre.get("status") == 409 and "share_required" in pre.get("body", ""), f"status={pre.get('status')} body={pre.get('body','')[:100]}")
        ev["pre_share_discover"] = pre
        r, prep = call("resonance_prepare_thought", {"request_id": "harness-prep-1"})
        ok("WRITE 1: resonance_prepare_thought -> private (discoverable=false)", prep.get("discoverable") is False, json.dumps({k: prep.get(k) for k in ("discoverable", "draft_ready", "session_id", "state")}))
        ev["header_after_prepare"] = text(pg, "#header-consent"); ev["pill_after_prepare"] = text(pg, "#webmcp-status")
        r, prev = call("resonance_get_share_preview", {})
        dna = prev.get("thought_dna") or (prev.get("will_become_discoverable") or {}).get("thought") or {}
        ok("READ: resonance_get_share_preview returns confirmation_token + Thought DNA", bool(prev.get("confirmation_token")), f"nodes={len(dna.get('nodes', []))} relations={len(dna.get('relations', []))}")
        r, dl = call("resonance_discover", {"source": "live"})
        ok("nothing discoverable before confirm: LIVE discover refuses (no shared thought)", isinstance(r, dict) and (r.get("isError") or (dl.get("error") if isinstance(dl, dict) else None)), json.dumps(r)[:160])
        pg.screenshot(path=str(out / "browser_02_preview_private.png"))
        r, sh = call("resonance_share_prepared_thought", {"request_id": "harness-share-1", "confirm": True, "confirmation_token": prev["confirmation_token"]})
        ok("WRITE 2: explicit share -> discoverable=true", sh.get("discoverable") is True or sh.get("shared") is True, json.dumps({k: sh.get(k) for k in ("discoverable", "shared", "session_id")}))
        pg.wait_for_timeout(800)
        ev["header_after_share"] = text(pg, "#header-consent"); ev["pill_after_share"] = text(pg, "#webmcp-status")
        ok("visible UI update after share (header/pill changed)", ev["header_after_share"] != ev["header_before"] or "shared" in (ev["pill_after_share"] or "").lower(),
           f"header: {ev['header_before']!r} -> {ev['header_after_share']!r}; pill: {ev['pill_after_share']!r}")
        pg.screenshot(path=str(out / "browser_03_after_share.png"))
        r2, sh2 = call("resonance_share_prepared_thought", {"request_id": "harness-share-1", "confirm": True, "confirmation_token": prev["confirmation_token"]})
        ok("idempotent retry (same request_id) returns committed result", sh2.get("session_id") == sh.get("session_id"), f"{sh2.get('session_id')} == {sh.get('session_id')}")
        r, dl = call("resonance_discover", {"source": "live"})
        ms = dl.get("matches_in_backend_order", dl.get("matches", []))
        ok("READ: LIVE discover after share returns live matches", dl.get("source") == "live" and len(ms) > 0, f"result_id={dl.get('result_id')} n={len(ms)}")
        pg.wait_for_timeout(800)
        # click Live MCP source to make cards visible
        try:
            pg.click("#source-live", timeout=3000); pg.wait_for_timeout(1500)
        except Exception as e:
            console.append(f"harness: click #source-live failed: {e}")
        cards = pg.locator(".match-card, [data-match-id], .result-card, .match").count()
        ok("visible match cards/results after discover", cards > 0, f"cards={cards}")
        ev["pill_after_discover"] = text(pg, "#webmcp-status"); ev["response_summary"] = text(pg, "#response-summary")
        pg.screenshot(path=str(out / "browser_04_after_discover.png"))
        first = ms[0] if ms else {}
        r, gm = call("resonance_get_match", {"result_id": dl.get("result_id"), "session_id": first.get("session_id")})
        ok("READ: resonance_get_match returns evidence for a live match", bool(gm) and not (isinstance(r, dict) and r.get("isError")), f"keys={sorted(gm.keys())[:8] if isinstance(gm, dict) else gm}")
        r, rv = call("resonance_update_consent", {"request_id": "harness-revoke-1", "shared": False})
        ok("WRITE 3: revoke consent (shared=false)", not (isinstance(r, dict) and r.get("isError")), json.dumps(rv)[:160])
        pg.wait_for_timeout(800)
        ev["header_after_revoke"] = text(pg, "#header-consent"); ev["pill_after_revoke"] = text(pg, "#webmcp-status")
        r, dl2 = call("resonance_discover", {"source": "live"})
        ok("after revoke: LIVE discover fails closed / thought not discoverable", (isinstance(r, dict) and r.get("isError")) or dl2.get("error"), json.dumps(r)[:160])
        r, gm2 = call("resonance_get_match", {"result_id": dl.get("result_id"), "session_id": first.get("session_id")})
        ok("after revoke: old result_id evidence fails closed", (isinstance(r, dict) and r.get("isError")) or (isinstance(gm2, dict) and gm2.get("error")), json.dumps(r)[:160])
        pg.screenshot(path=str(out / "browser_05_after_revoke.png"))
        ev["console_harness"] = console[:60]
        b.close()

    ev["checks"] = checks
    ev["summary"] = f"{sum(c['ok'] for c in checks)}/{len(checks)} checks passed"
    print("\n" + ev["summary"])
    (out / "browser_harness.json").write_text(json.dumps(ev, indent=2) + "\n")
    return 0 if all(c["ok"] for c in checks if "NATIVE" not in c["step"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
