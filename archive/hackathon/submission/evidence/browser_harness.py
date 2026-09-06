#!/usr/bin/env python3
"""Browser evidence for the WebMCP page (supporting evidence, labelled honestly).

Loads the competition page in headless Chromium via Playwright, records whether a
NATIVE `document.modelContext` exists, and then runs the six R10 tools one of two
ways — the report always says which:

* **NATIVE** — the browser exposes `document.modelContext`, so the tools are
  discovered with `getTools({})` and invoked with `executeTool(tool, argsJson, {})`
  through the browser's own agent surface. This is native WebMCP evidence.
* **SHIM** — no agent surface, so a minimal modelContext shim is installed BEFORE
  page scripts and the page's own `registerWebMCP()` registers its tools through
  the standard `registerTool(tool, {signal})` call, whose `execute` functions are
  then invoked directly. This proves the page-side registration and the tool
  contract, and is NOT native WebMCP discovery.

Which one you get is a property of the browser, not of the product. Stock Chromium
has no `document.modelContext`. **Google Chrome 152.0.7977.83 does, when launched
with `--enable-features=WebMCP`** — the flag this harness always passes — so
pointing `--exe` at a Chrome 152+ install is what turns this into native evidence:

    python3 submission/evidence/browser_harness.py https://<origin> \
        --exe "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
        --out submission/evidence/<dir>

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

# demo/ui/app.mjs: PRIMARY_LIMIT — how many primary match cards the rail renders.
PRIMARY_LIMIT = 4

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

# The NATIVE surface, exercised only when the browser really exposes it. Shape
# measured on Google Chrome 152.0.7977.83 with --enable-features=WebMCP:
#
#   document.modelContext instanceof ModelContext
#   prototype: registerTool, getTools, executeTool, ontoolchange
#   getTools({})           -> Promise<Array>, entries own {name, title,
#                             description, inputSchema, origin, window}
#   executeTool(tool, argsJsonString, {}) -> Promise<string>, the tool result
#                             serialized as JSON; the page's own execute()
#                             receives the PARSED object
#   passing an object instead of a JSON string rejects with
#   "UnknownError: Failed to parse input arguments"
#
# This is the path that makes Card A steps 2-9 native evidence rather than
# page-side registration evidence: the tools are discovered and invoked through
# the browser's own agent surface, exactly as an agent-capable browser would.
NATIVE_LIST = """
async () => (await document.modelContext.getTools({})).map(t => t.name)
"""

NATIVE_CALL = """
async ([name, args]) => {
  const mc = document.modelContext;
  const tools = await mc.getTools({});
  const tool = tools.find(t => t.name === name);
  if (!tool) throw new Error('tool not registered: ' + name);
  try {
    // executeTool takes the arguments as a JSON STRING and resolves with the
    // tool result as a JSON STRING.
    const raw = await mc.executeTool(tool, JSON.stringify(args || {}), {});
    return typeof raw === 'string' ? JSON.parse(raw) : JSON.parse(JSON.stringify(raw));
  } catch (e) {
    return {isError: true, error: e.code || e.name || 'error', status: e.status || null, message: String(e.message || e)};
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
    # Some runners (sandboxed CI, an agent container) reach the public internet
    # only through an HTTP proxy. Chromium does not read HTTPS_PROXY on its own,
    # so pass it through; the origin under test is public either way.
    ap.add_argument("--proxy", default=os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
                    help="HTTP proxy for the browser (default: $HTTPS_PROXY); pass '' to force a direct connection")
    # Escape hatch for constrained runners. Certificate verification is never
    # disabled here and must not be: only add flags that change transport, e.g.
    # --browser-arg=--ssl-version-max=tls1.2 when an egress relay cannot carry
    # a TLS 1.3 handshake.
    ap.add_argument("--browser-arg", action="append", default=[], dest="browser_args",
                    help="extra Chromium flag (repeatable); never use it to disable certificate checks")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    ev = {"origin": args.origin, "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "steps": []}
    checks = []

    def ok(step, cond, detail="", advisory=False):
        # `advisory` marks a check that records a fact about the RUNNER rather
        # than about the product — today only the native-capability probe. It
        # is reported like any other check but is excluded from the exit code,
        # because "this browser has no WebMCP" must not turn a correct product
        # run red. Everything else, including every tool call made through a
        # native surface when one exists, counts.
        checks.append({"step": step, "ok": bool(cond), "advisory": bool(advisory), "detail": detail})
        print(f"[{'PASS' if cond else 'FAIL'}] {step}" + (f" — {detail}" if detail else ""))
        return bool(cond)

    with sync_playwright() as p:
        launch = {"args": ["--enable-features=WebMCP,WebMCPTesting", *args.browser_args]}
        if args.exe:
            launch["executable_path"] = args.exe
        if args.proxy:
            launch["proxy"] = {"server": args.proxy}
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
           f"typeof document.modelContext={native}; navigator.modelContext={native_nav} "
           f"in {b.version}. A fact about the RUNNER, not the product: absent in a stock "
           f"browser, present in Google Chrome 152+ launched with --enable-features=WebMCP "
           f"(the harness passes that flag). Advisory: excluded from the exit code.",
           advisory=True)
        ev["native_status_pill"] = text(pg, "#webmcp-status")
        # The capability pill has to track the browser in BOTH directions. It
        # said "WebMCP · private" in a browser with no document.modelContext —
        # indistinguishable from a browser where registration succeeded —
        # because the consent updater wrote over it. Card A step 1 tells a
        # tester to stop and report the browser when it reads "unavailable",
        # so this check is not advisory: it holds in either browser.
        ok("the capability pill agrees with the browser "
           "(says 'unavailable' exactly when document.modelContext is absent)",
           ("unavailable" in (ev["native_status_pill"] or "").lower()) == (native == "undefined"),
           f"pill={ev['native_status_pill']!r}; typeof document.modelContext={native}")
        ev["native_contract"] = pg.evaluate("window.__resonanceWebMCP || null")
        ok("page exposes WebMCP contract + six tool names", bool(ev["native_contract"]) and len(ev["native_contract"].get("toolNames", [])) == 6,
           json.dumps(ev["native_contract"]))
        pg.screenshot(path=str(out / "browser_01_native_load.png"), full_page=False)
        ev["console_native"] = console[:40]
        b.close()

        # 2) tool run. With a real agent surface the tools are discovered and
        #    invoked through the browser itself (NATIVE); without one the shim
        #    stands in so the page-side contract can still be exercised. The
        #    two are never conflated: `ev["mode"]` and every check label say
        #    which one produced the evidence.
        is_native = native != "undefined"
        mode = "NATIVE" if is_native else "SHIM"
        ev["mode"] = mode
        b = p.chromium.launch(**launch)
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        if not is_native:
            ctx.add_init_script(SHIM)
        pg = ctx.new_page()
        console = []
        pg.on("console", lambda m: console.append(f"{m.type}: {m.text}"))
        pg.goto(args.origin + "/", wait_until="networkidle", timeout=60000)
        pg.wait_for_timeout(1500)
        names = pg.evaluate(NATIVE_LIST) if is_native else pg.evaluate(
            "document.modelContext.__tools.map(t => t.name)")
        six = ["resonance_prepare_thought", "resonance_get_share_preview", "resonance_share_prepared_thought",
               "resonance_discover", "resonance_get_match", "resonance_update_consent"]
        ok(f"{mode}: page registered its tools via document.modelContext.registerTool "
           f"(six R10 tools + collaboration/workspace tools)",
           all(n in names for n in six), f"{len(names)} tools: " + ", ".join(names))
        if is_native:
            # Only meaningful natively: the browser's own tool list is what an
            # agent panel would show, including the schema it would call with.
            shape = pg.evaluate("""async () => {
              const t = (await document.modelContext.getTools({})).find(x => x.name === 'resonance_discover');
              return t ? {name: t.name, keys: Object.keys(t), hasInputSchema: !!t.inputSchema,
                          origin: t.origin, description: (t.description || '').slice(0, 80)} : null;
            }""")
            ev["native_tool_shape"] = shape
            ok("NATIVE: the browser's own getTools() exposes the tool with its input schema",
               bool(shape) and shape.get("hasInputSchema") is True, json.dumps(shape))
        ok(f"{mode}: status pill reports registration",
           (text(pg, "#webmcp-status") or "").startswith("WebMCP ·"), text(pg, "#webmcp-status"))
        if is_native:
            # The capability pill must say the browser HAS a surface. A build
            # without document.modelContext must read "WebMCP · unavailable";
            # the consent state belongs to #header-consent, not here.
            ok("NATIVE: the capability pill does not report 'unavailable' in a WebMCP browser",
               "unavailable" not in (text(pg, "#webmcp-status") or "").lower(),
               text(pg, "#webmcp-status"))
        ev["harness_tools"] = names
        ev["header_before"] = text(pg, "#header-consent")

        def call(name, a):
            r = pg.evaluate(NATIVE_CALL if is_native else CALL, [name, a])
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
        # What the page renders is `selectPrimaryMatches(payload)` (demo/ui/app.mjs):
        # matches that are `display.share_state == "discoverable"`, carry no
        # `hard_rejection`, and are not `negative` — capped at PRIMARY_LIMIT. So
        # `cards > 0` was never the right expectation: against a corpus that holds
        # no resonance for this thought EVERY live match is `negative`, the rail is
        # correctly empty, and the old check went red for correct fail-closed
        # behaviour. Assert the exact relation instead, which is strictly stronger:
        # as many cards as the payload has eligible matches, and the shell in
        # `ready` exactly when that count is non-zero.
        #
        # The expectation is derived from the response THE PAGE fetches
        # (`/api/discover?source=live`, the R8 contract the renderer consumes),
        # read back from the page's own session, not from the tool payload above.
        rendered = pg.evaluate("""async () => {
          const r = await fetch('/api/discover?source=live', {cache: 'no-store', credentials: 'same-origin'});
          return {status: r.status, body: await r.json().catch(() => null)};
        }""")
        rendered_body = rendered.get("body") or {}
        rendered_matches = rendered_body.get("matches") or []
        eligible = [m for m in rendered_matches
                    if isinstance(m, dict)
                    and (m.get("display") or {}).get("share_state") == "discoverable"
                    and m.get("hard_rejection") is None
                    and m.get("mode_classification") != "negative"]
        expected_cards = min(len(eligible), PRIMARY_LIMIT)
        cards = pg.locator(".match-card").count()
        shell = pg.evaluate("() => document.getElementById('app-shell').dataset.state")
        shown = (text(pg, "#shown-count") or "").strip()
        ev["rendered_discovery"] = {
            "status": rendered.get("status"),
            "matches": len(rendered_matches),
            "eligible": len(eligible),
            "expected_cards": expected_cards,
            "cards": cards,
            "app_state": shell,
            "shown_count": shown,
            "classifications": sorted({str(m.get("mode_classification")) for m in rendered_matches}),
        }
        ok("visible match cards equal the payload's eligible matches (cards == min(eligible, 4))",
           cards == expected_cards,
           f"cards={cards} expected={expected_cards} from {len(rendered_matches)} returned "
           f"({len(eligible)} eligible; classifications="
           f"{ev['rendered_discovery']['classifications']})")
        ok("the shell state agrees with the payload (ready iff a resonance is shown)",
           shell in ("ready", "empty") and (shell == "ready") == (expected_cards > 0),
           f"data-state={shell!r} expected_cards={expected_cards}")
        ok("the visible count agrees with the cards actually rendered",
           shown == f"{cards:02d} shown", f"shown-count={shown!r} cards={cards}")
        if expected_cards == 0:
            # An empty rail must be its own honest state, not a match count over
            # nothing (the R9 defect fixed in #167).
            summary = text(pg, "#response-summary") or ""
            ok("an empty rail reports zero resonances rather than a bare match count",
               "0 resonances" in summary, f"response-summary={summary!r}")
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
    # Previously: every check whose label contained "NATIVE" was excluded, which
    # was fine while the only such check was the capability probe. Now that a
    # WebMCP browser really executes the tools natively, those results must
    # count, so the exclusion is by explicit `advisory` flag instead of by a
    # substring of the label.
    return 0 if all(c["ok"] for c in checks if not c.get("advisory")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
