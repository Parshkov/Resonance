"""Phase 5 — headless Chromium (Playwright) against the public origin.

Run 1: plain Chromium            -> is native document.modelContext present?
Run 2: --enable-features=WebMCP,WebMCPTesting -> present now?
Run 3: HARNESS — inject a minimal document.modelContext shim BEFORE page scripts
       so the page's own webmcp.mjs registers its tools into window.__harnessTools,
       then execute those page-registered tools in order. This is NOT native
       WebMCP discovery; it is the page's tool implementations driven by a shim.
Never prints cookies/tokens. Confirmation token from the preview is used but not recorded.
"""
from __future__ import annotations
import json, os, sys, re
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

ORIGIN = sys.argv[1] if len(sys.argv) > 1 else "https://resonance-production-cfe3.up.railway.app"
OUT = os.path.dirname(os.path.abspath(__file__))
REDACT_KEYS = {"confirmation_token", "csrf_token", "csrf", "access_token", "refresh_token", "cookie", "mcp_key"}


def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def redact(obj):
    if isinstance(obj, dict):
        return {k: ("<redacted>" if k in REDACT_KEYS else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj


def slim_matches(res):
    if not isinstance(res, dict): return res
    out = {k: v for k, v in res.items() if k not in ("matches", "rejected")}
    for key in ("matches", "rejected"):
        rows = res.get(key) or []
        out[key + "_count"] = len(rows)
        out[key + "_slim"] = [{"session_id": m.get("session_id"), "scores": m.get("scores"),
                               "preserved_relation_count": (m.get("evidence") or {}).get("preserved_relation_count"),
                               "topic": (m.get("display") or {}).get("topic")} for m in rows[:6]]
    return out


HEADER_JS = """() => {
  const h = document.querySelector('header') || document.querySelector('.topbar') || document.body;
  const consent = document.getElementById('header-consent');
  const status = document.getElementById('webmcp-status');
  return {
    header_innerText: (h.innerText || '').slice(0, 1500),
    header_consent_text: consent ? consent.innerText : null,
    header_consent_data_shared: consent ? consent.dataset.shared : null,
    webmcp_status_text: status ? status.innerText : null,
    has_private_pill: /Private/.test(consent ? consent.innerText : (h.innerText || '')),
    has_webmcp_badge: !!status || /WebMCP/.test(h.innerText || ''),
  };
}"""
PROBE_JS = """() => ({
  typeof_document_modelContext: typeof document.modelContext,
  typeof_navigator_modelContext: typeof navigator.modelContext,
  resonanceWebMCP: window.__resonanceWebMCP || null,
  title: document.title,
  userAgent: navigator.userAgent,
})"""

report = {"origin": ORIGIN, "started_utc": now(), "runs": {}}


def launch(p, args=None):
    # Sandbox egress workaround (not a product concern): this container reaches
    # the internet only through an HTTPS CONNECT proxy whose relay drops
    # Chromium's TLS 1.3 ClientHello (tunnel closed after ~1750 B sent / 39 B
    # received). Capping Chromium at TLS 1.2 makes the tunnel work.
    kw = {"headless": True, "args": ["--ssl-version-max=tls1.2"] + list(args or [])}
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        kw["proxy"] = {"server": proxy}
    try:
        return p.chromium.launch(**kw)
    except Exception as exc:  # fall back to the pre-installed binary
        report.setdefault("launch_notes", []).append(f"default launch failed: {str(exc)[:200]}; using /opt/pw-browsers/chromium")
        kw["executable_path"] = "/opt/pw-browsers/chromium"
        return p.chromium.launch(**kw)


def probe_run(p, name, args=None, screenshot=None):
    browser = launch(p, args)
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    page = ctx.new_page()
    console = []
    page.on("console", lambda m: console.append(f"{m.type}: {m.text[:200]}"))
    page.goto(ORIGIN + "/", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(1500)
    info = page.evaluate(PROBE_JS)
    info.update(page.evaluate(HEADER_JS))
    info["chromium_version"] = browser.version
    info["args"] = args or []
    info["console_tail"] = console[-8:]
    if screenshot:
        page.screenshot(path=os.path.join(OUT, screenshot), full_page=True)
        info["screenshot"] = screenshot
    browser.close()
    report["runs"][name] = info
    print(f"[{name}] chromium={info['chromium_version']} typeof document.modelContext={info['typeof_document_modelContext']} "
          f"navigator={info['typeof_navigator_modelContext']} title={info['title']!r} status={info['webmcp_status_text']!r}")
    return info


SHIM = """
(() => {
  window.__harnessTools = [];
  window.__harnessShim = true;
  document.modelContext = {
    registerTool(tool) { window.__harnessTools = (window.__harnessTools || []).concat([tool]); },
  };
})();
"""


def harness_run(p):
    browser = launch(p)
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    ctx.add_init_script(SHIM)
    page = ctx.new_page()
    console = []
    page.on("console", lambda m: console.append(f"{m.type}: {m.text[:200]}"))
    page.goto(ORIGIN + "/", wait_until="networkidle", timeout=60000)
    page.wait_for_function("() => (window.__harnessTools || []).length >= 6", timeout=20000)
    page.wait_for_timeout(1000)
    run = {"label": "HARNESS: page-registered tools executed via injected modelContext shim, NOT native WebMCP discovery",
           "chromium_version": browser.version, "steps": []}
    run["registered_tool_names"] = page.evaluate("() => window.__harnessTools.map(t => t.name)")
    run["registered_tool_schemas_ok"] = page.evaluate(
        "() => window.__harnessTools.every(t => t.inputSchema && typeof t.execute === 'function' && t.annotations)")
    run["state_after_load"] = page.evaluate(HEADER_JS)
    print(f"[harness] tools registered: {run['registered_tool_names']}")

    def call(tool, args, label, screenshot=None):
        js = """async ([name, args]) => {
          const t = (window.__harnessTools || []).find(x => x.name === name);
          if (!t) return {__missing: true};
          try { return {ok: true, result: await t.execute(args)}; }
          catch (e) { return {ok: false, error: {message: String(e && e.message || e), code: e && e.code, status: e && e.status}}; }
        }"""
        res = page.evaluate(js, [tool, args])
        page.wait_for_timeout(600)
        step = {"step": label, "tool": tool, "args": redact(args), "ok": res.get("ok"),
                "error": res.get("error"), "result": redact(slim_matches(res.get("result"))),
                "header": page.evaluate(HEADER_JS)}
        if screenshot:
            page.screenshot(path=os.path.join(OUT, screenshot), full_page=True); step["screenshot"] = screenshot
        run["steps"].append(step)
        print(f"[harness] {label}: ok={res.get('ok')} status={step['header']['webmcp_status_text']!r} consent={step['header']['header_consent_text']!r}"
              + (f" error={res.get('error')}" if not res.get("ok") else ""))
        return res.get("result") if res.get("ok") else None

    call("resonance_discover", {"source": "replay"}, "1 discover(replay)")
    call("resonance_prepare_thought", {"request_id": "pulse-1"}, "2 prepare_thought(pulse-1)")
    preview = call("resonance_get_share_preview", {}, "3 get_share_preview")
    token = (preview or {}).get("confirmation_token") or ""
    run["preview_had_confirmation_token"] = bool(token)
    share = call("resonance_share_prepared_thought", {"request_id": "pulse-2", "confirm": True, "confirmation_token": token},
                 "4 share_prepared_thought(pulse-2, confirm=true)", screenshot="phase5_after_share.png")
    disc = call("resonance_discover", {"source": "live"}, "5 discover(live)", screenshot="phase5_after_discover.png")
    first = ((disc or {}).get("matches") or [None])[0] if isinstance(disc, dict) else None
    if isinstance(disc, dict) and disc.get("result_id") and first:
        call("resonance_get_match", {"result_id": disc["result_id"], "session_id": first["session_id"]},
             "6 get_match(first live match)")
    else:
        run["steps"].append({"step": "6 get_match", "skipped": True, "reason": "no result_id or no matches from live discover",
                             "live_keys": sorted((disc or {}).keys()) if isinstance(disc, dict) else None})
    call("resonance_update_consent", {"request_id": "pulse-3", "shared": False}, "7 update_consent(shared=false)")
    run["console_tail"] = console[-12:]
    browser.close()
    report["runs"]["harness"] = run
    return run


with sync_playwright() as p:
    native = probe_run(p, "native_plain", screenshot="phase5_page.png")
    flagged = probe_run(p, "native_with_flags", args=["--enable-features=WebMCP,WebMCPTesting"])
    native_present = native["typeof_document_modelContext"] != "undefined" or flagged["typeof_document_modelContext"] != "undefined"
    report["native_modelContext_present"] = native_present
    if not native_present:
        harness_run(p)
    else:
        report["note"] = "native modelContext present — harness not needed"

report["finished_utc"] = now()
blob = json.dumps(report, indent=2, default=str)
assert "confirmation_token\": \"" not in blob or "<redacted>" in blob
with open(os.path.join(OUT, "phase5_browser.json"), "w") as f:
    f.write(blob)

h = report["runs"].get("harness") or {}
lines = [
    "# Phase 5 — browser evidence (Playwright headless Chromium) against public origin", "",
    f"Origin: {ORIGIN}", f"Started: {report['started_utc']}  Finished: {report['finished_utc']}", "",
    f"**NATIVE document.modelContext: {'present' if report['native_modelContext_present'] else 'absent'} in Playwright Chromium "
    f"{native['chromium_version']}; harness run = page-registered tools executed via injected modelContext shim, NOT native WebMCP discovery**", "",
    "## Run 1 — plain Chromium", "",
    f"- typeof document.modelContext: `{native['typeof_document_modelContext']}`",
    f"- typeof navigator.modelContext: `{native['typeof_navigator_modelContext']}`",
    f"- window.__resonanceWebMCP: `{json.dumps(native['resonanceWebMCP'])}`",
    f"- page title: `{native['title']}`",
    f"- header consent text: `{native['header_consent_text']}` (Private pill: {native['has_private_pill']})",
    f"- WebMCP badge (#webmcp-status): `{native['webmcp_status_text']}` (badge present: {native['has_webmcp_badge']})",
    f"- screenshot: phase5_page.png", "",
    "```", native["header_innerText"], "```", "",
    "## Run 2 — Chromium with --enable-features=WebMCP,WebMCPTesting", "",
    f"- typeof document.modelContext: `{flagged['typeof_document_modelContext']}`",
    f"- typeof navigator.modelContext: `{flagged['typeof_navigator_modelContext']}`",
    f"- WebMCP badge: `{flagged['webmcp_status_text']}`", "",
]
if h:
    lines += ["## Run 3 — HARNESS (injected `document.modelContext` shim; NOT native WebMCP)", "",
              f"- registered tool names (from the page's own webmcp.mjs): `{json.dumps(h.get('registered_tool_names'))}`",
              f"- all tools carry inputSchema/annotations/execute: {h.get('registered_tool_schemas_ok')}",
              f"- state after load: consent=`{h['state_after_load']['header_consent_text']}` status=`{h['state_after_load']['webmcp_status_text']}`",
              f"- preview returned a confirmation token: {h.get('preview_had_confirmation_token')} (value not recorded)", "",
              "| step | ok | header consent | WebMCP status | result summary |", "|---|---|---|---|---|"]
    for s in h["steps"]:
        if s.get("skipped"):
            lines.append(f"| {s['step']} | skipped | | | {s['reason']} |"); continue
        r = s.get("result") if isinstance(s.get("result"), dict) else {}
        summary = {k: r.get(k) for k in ("result_id", "source", "session_id", "shared", "discoverable", "draft_ready",
                                          "matches_count", "rejected_count", "committed", "state", "mode") if k in r}
        if s.get("error"): summary["error"] = s["error"]
        lines.append(f"| {s['step']} | {s.get('ok')} | {s['header']['header_consent_text']} | {s['header']['webmcp_status_text']} | `{json.dumps(summary, default=str)[:260]}` |")
    lines += ["", "Screenshots: phase5_after_share.png, phase5_after_discover.png. Full detail (tokens redacted): phase5_browser.json"]
with open(os.path.join(OUT, "phase5_browser.md"), "w") as f:
    f.write("\n".join(lines) + "\n")
print("wrote phase5_browser.md")
