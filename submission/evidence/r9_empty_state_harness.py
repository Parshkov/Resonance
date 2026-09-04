#!/usr/bin/env python3
"""R9 presentation regression: what the page shows when a discovery returns
candidates but none of them clear the resonance bar, and what survives an error.

    python3 -m demo.ui.serve --port 8901 &
    python3 submission/evidence/r9_empty_state_harness.py http://127.0.0.1:8901 \
        --exe /path/to/chrome --out submission/evidence/<dir>

Why this exists. `primary_matches()` drops every `negative` match by design, so
against a corpus that holds no resonance for the visible thought the primary rail
is correctly empty. That is right. What was wrong was everything around it: the
empty result travelled through the *error* path, and that path cleared only the
match list — leaving the previous source's evidence panel, mapping rows, relation
chips, drawer contents, contradiction card, map markers and response counts on
screen. A person then read "10 matches · 5 rejected" over an empty rail, next to
another source's named evidence. Observed on production at `0aea577`.

The discovery response is stubbed at the network layer with the SHAPE seen on
production (every returned candidate refused as a resonance) so the real
`app.mjs` renders it in a real browser. Nothing here talks to the engine.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "src" / "discovery" / "fixtures" / "example_response.json"


def all_refused(payload: dict) -> dict:
    """The accepted fixture, with every match refused as a resonance."""
    out = json.loads(json.dumps(payload))
    for match in out["matches"]:
        match["mode_classification"] = "negative"
        match["hard_rejection"] = None
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base", help="origin serving the R9 page, e.g. http://127.0.0.1:8901")
    ap.add_argument("--out", default=None, help="directory for the JSON report and screenshot")
    ap.add_argument("--exe", default=os.environ.get("CHROME_EXE"))
    ap.add_argument("--proxy", default=os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
                    help="HTTP proxy for the browser (default: $HTTPS_PROXY); pass '' for a direct connection")
    ap.add_argument("--browser-arg", action="append", default=[], dest="browser_args",
                    help="extra Chromium flag (repeatable); never use it to disable certificate checks")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    fixture = json.loads(FIXTURE.read_text())

    checks: list[dict] = []

    def ok(step: str, cond: bool, detail: str = "") -> bool:
        checks.append({"step": step, "ok": bool(cond), "detail": detail})
        print(f"[{'PASS' if cond else 'FAIL'}] {step}" + (f" — {detail}" if detail else ""))
        return bool(cond)

    def text(page, selector: str) -> str | None:
        try:
            return page.locator(selector).first.inner_text(timeout=1500).strip()
        except Exception:  # noqa: BLE001
            return None

    with sync_playwright() as p:
        launch: dict = {"args": [*args.browser_args]}
        if args.exe:
            launch["executable_path"] = args.exe
        if args.proxy:
            launch["proxy"] = {"server": args.proxy}
        browser = p.chromium.launch(**launch)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        console: list[str] = []
        page.on("console", lambda m: console.append(f"{m.type}: {m.text}"))
        page.on("pageerror", lambda e: console.append(f"pageerror: {e}"))
        page.goto(base + "/", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1200)

        # Baseline: a normal render populates every result surface. The values
        # captured here are exactly what must NOT survive into another state.
        ok("baseline REPLAY renders match cards", page.locator(".match-card").count() > 0,
           f"cards={page.locator('.match-card').count()}")
        baseline_summary = text(page, "#response-summary")
        baseline_kicker = text(page, "#evidence-kicker")
        ok("baseline populates evidence and drawer",
           page.locator(".mapping-row").count() > 0 and page.locator(".drawer-row").count() > 0,
           f"summary={baseline_summary!r} kicker={baseline_kicker!r}")

        # 1) Discovery succeeds; nothing clears the resonance bar.
        page.route("**/api/discover?source=live", lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps(all_refused(fixture))))
        page.click("#source-live", timeout=5000)
        page.wait_for_timeout(2000)

        state = page.evaluate("() => document.getElementById('app-shell').dataset.state")
        ok("an empty result is its own state, not an error", state == "empty", f"data-state={state!r}")
        ok("no match cards are shown", page.locator(".match-card").count() == 0,
           f"cards={page.locator('.match-card').count()}")
        summary = text(page, "#response-summary")
        ok("the summary no longer claims matches that are not shown",
           bool(summary) and "0 resonances" in summary and summary != baseline_summary,
           f"summary={summary!r} (was {baseline_summary!r})")
        kicker = text(page, "#evidence-kicker")
        ok("the evidence panel drops the previous source's identity",
           kicker != baseline_kicker, f"kicker={kicker!r} (was {baseline_kicker!r})")
        ok("stale mapping rows are gone", page.locator(".mapping-row").count() == 0,
           f"mapping_rows={page.locator('.mapping-row').count()}")
        ok("stale relation chips are gone", page.locator(".relation-chip").count() == 0,
           f"chips={page.locator('.relation-chip').count()}")
        ok("the returned-but-refused candidates stay inspectable",
           page.locator(".drawer-row").count() > 0, f"drawer_rows={page.locator('.drawer-row').count()}")
        ok("the map reports zero resonances", "0 resonances" in (text(page, "#map-status-text") or ""),
           f"map_status={text(page, '#map-status-text')!r}")
        ok("the heading says why nothing is shown",
           "cleared the resonance bar" in (text(page, "#evidence-heading") or "").lower(),
           f"heading={text(page, '#evidence-heading')!r}")
        if args.out:
            Path(args.out).mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(Path(args.out) / "r9_empty_state.png"))

        # 2) A real failure must leave nothing of any previous render behind.
        page.click("#source-replay", timeout=5000)
        page.wait_for_timeout(1500)
        ok("replay renders again after the empty state", page.locator(".match-card").count() > 0,
           f"cards={page.locator('.match-card').count()}")
        page.route("**/api/discover?source=live", lambda route: route.fulfill(
            status=500, content_type="application/json", body=json.dumps({"error": "injected failure"})))
        page.click("#source-live", timeout=5000)
        page.wait_for_timeout(2000)
        state = page.evaluate("() => document.getElementById('app-shell').dataset.state")
        ok("a failure is reported as an error", state == "error", f"data-state={state!r}")
        leftovers = page.evaluate("""() => ({
            cards: document.querySelectorAll('.match-card').length,
            mappings: document.querySelectorAll('.mapping-row').length,
            chips: document.querySelectorAll('.relation-chip').length,
            drawer: document.querySelectorAll('.drawer-row').length,
            markers: document.querySelectorAll('#marker-layer > *').length,
            connections: document.querySelectorAll('#connection-layer > *').length,
            summary: (document.getElementById('response-summary')||{}).textContent,
            kicker: (document.getElementById('evidence-kicker')||{}).textContent,
            contradictionHidden: (document.getElementById('contradiction-card')||{}).hidden,
        })""")
        ok("the error state leaves no result data from the previous source",
           all(leftovers[k] == 0 for k in ("cards", "mappings", "chips", "drawer", "markers", "connections"))
           and leftovers["contradictionHidden"] is True
           and "matches" not in (leftovers["summary"] or ""),
           json.dumps(leftovers))

        # Uncaught exceptions are the real signal. Console *resource* errors are
        # expected: a replay-only demo server has no live /api/context, and the
        # 500 on /api/discover?source=live is injected above.
        uncaught = [c for c in console if c.startswith("pageerror")]
        ok("no uncaught JavaScript exceptions", not uncaught, "; ".join(uncaught[:3]))
        unexpected = [c for c in console
                      if c.startswith("error:") and "404" not in c and "500" not in c]
        ok("no unexpected console errors", not unexpected, "; ".join(unexpected[:3]))
        browser.close()

    failed = [c for c in checks if not c["ok"]]
    summary_line = f"{len(checks) - len(failed)}/{len(checks)} checks passed"
    print("\n" + summary_line + (f"; FAILED: {', '.join(c['step'] for c in failed)}" if failed else ""))
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "r9_empty_state.json").write_text(
            json.dumps({"base": base, "checks": checks, "summary": summary_line}, indent=2) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
