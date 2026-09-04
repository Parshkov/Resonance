"""P6 run 2: scripted own-thought flow through the page's WebMCP tools (shim), plus OAuth consent page screenshot."""
import json, os, sys, time, urllib.request
from playwright.sync_api import sync_playwright
sys.path.insert(0, "/home/user/Resonance/submission/evidence")
from browser_harness import SHIM, CALL, text  # noqa
ORIGIN = "https://resonance-production-cfe3.up.railway.app"
OUT = "/home/user/Resonance/submission/evidence/public-origin-3c7dc80"
THOUGHT = {"topic": "Panic buying after a shortage rumour", "domain": "consumer-economics",
           "nodes": [{"id": "b0", "label": "supply shortage rumour", "role": "problem"},
                     {"id": "b1", "label": "synchronized bulk purchases", "role": "mechanism"},
                     {"id": "b2", "label": "demand amplification", "role": "state"},
                     {"id": "b3", "label": "empty shelves", "role": "outcome"},
                     {"id": "b5", "label": "staggered restocking", "role": "method"}],
           "relations": [{"source": "b0", "target": "b1", "type": "causes"}, {"source": "b1", "target": "b2", "type": "causes"},
                         {"source": "b2", "target": "b3", "type": "causes"}, {"source": "b3", "target": "b1", "type": "causes"},
                         {"source": "b5", "target": "b2", "type": "prevents"}]}
ev = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "checks": []}
def ok(step, cond, detail=""):
    ev["checks"].append({"step": step, "ok": bool(cond), "detail": detail}); print(f"[{'PASS' if cond else 'FAIL'}] {step}" + (f" — {detail}" if detail else "")); return bool(cond)
launch = {"args": ["--enable-features=WebMCP,WebMCPTesting", "--ssl-version-max=tls1.2"], "proxy": {"server": os.environ["HTTPS_PROXY"]},
          "executable_path": "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"}
with sync_playwright() as p:
    b = p.chromium.launch(**launch)
    ctx = b.new_context(viewport={"width": 1440, "height": 900}); ctx.add_init_script(SHIM)
    pg = ctx.new_page(); console = []; pg.on("console", lambda m: console.append(f"{m.type}: {m.text}"))
    pg.goto(ORIGIN + "/", wait_until="networkidle", timeout=60000); pg.wait_for_timeout(1000)
    def call(name, a):
        r = pg.evaluate(CALL, [name, a]); sc = r.get("structuredContent") if isinstance(r, dict) else None; return r, (sc or r)
    ok("page loaded with shim; tools registered", "resonance_prepare_thought" in pg.evaluate("document.modelContext.__tools.map(t => t.name)"), f"title={pg.title()!r} heading_before={text(pg, '#thought-heading')!r}")
    r, prep = call("resonance_prepare_thought", {"request_id": "pulse4-run2b-prep", "thought": THOUGHT})
    ok("resonance_prepare_thought WITH structured thought -> private draft", prep.get("discoverable") is False and not r.get("isError"), json.dumps({k: prep.get(k) for k in ("discoverable", "input_kind", "source_retention", "session_id")}))
    r, prev = call("resonance_get_share_preview", {})
    dna = prev.get("thought_dna") or (prev.get("will_become_discoverable") or {}).get("thought") or {}
    labels = {n.get("label") for n in dna.get("nodes", [])}
    ok("resonance_get_share_preview shows own 5 labels + confirmation_token", bool(prev.get("confirmation_token")) and labels == {n["label"] for n in THOUGHT["nodes"]}, f"nodes={len(dna.get('nodes', []))} relations={len(dna.get('relations', []))} topic={((prev.get('will_become_discoverable') or {}).get('presentation') or {}).get('topic')!r}")
    r, sh = call("resonance_share_prepared_thought", {"request_id": "pulse4-run2b-share", "confirm": True, "confirmation_token": prev.get("confirmation_token")})
    ok("resonance_share_prepared_thought (confirm+token) -> shared", sh.get("shared") is True and sh.get("discoverable") is True, json.dumps({k: sh.get(k) for k in ("shared", "discoverable", "session_id")}))
    r, dl = call("resonance_discover", {"source": "live"})
    ms = dl.get("matches_in_backend_order", dl.get("matches", []))
    ok("resonance_discover {source:live} -> live matches", dl.get("source") == "live" and len(ms) > 0, f"result_id={'set' if dl.get('result_id') else None} n={len(ms)}")
    pg.wait_for_timeout(2000)
    heading = text(pg, "#thought-heading"); status = text(pg, "#map-status-text")
    cards = pg.locator(".match-card"); n_cards = cards.count()
    card_classes = [cards.nth(i).get_attribute("class") for i in range(n_cards)]
    card_labels = [text(pg, f".match-card >> nth={i} >> .match-class, .match-card >> nth={i} >> [class*=class], .match-card >> nth={i} >> [class*=mode]") for i in range(n_cards)]
    ev.update({"thought_heading": heading, "map_status_text": status, "match_card_count": n_cards, "match_card_classes": card_classes, "match_card_labels": card_labels,
               "header_consent": text(pg, "#header-consent"), "webmcp_status": text(pg, "#webmcp-status")})
    ok("#thought-heading starts with 'Panic buying after a shortage rumour'", (heading or "").startswith("Panic buying after a shortage rumour"), f"heading={heading!r}")
    ok("#map-status-text captured", status is not None, f"map_status_text={status!r}")
    ok(".match-card count == 4", n_cards == 4, f"count={n_cards} classes={card_classes} labels={card_labels}")
    pg.screenshot(path=f"{OUT}/p6_live_own_thought_before_click.png", full_page=True)
    card_texts = [cards.nth(i).inner_text()[:90].replace("\n", " | ") for i in range(n_cards)]
    ev["match_card_texts_before_click"] = card_texts
    # variant: switch the page's source to Live MCP (what harness run 1 does) and re-read the same fields
    pg.click("#source-live", timeout=5000); pg.wait_for_timeout(2000)
    heading2 = text(pg, "#thought-heading"); status2 = text(pg, "#map-status-text"); cards2 = pg.locator(".match-card"); n2 = cards2.count()
    ev.update({"after_click_thought_heading": heading2, "after_click_map_status_text": status2, "after_click_match_card_count": n2,
               "after_click_match_card_classes": [cards2.nth(i).get_attribute("class") for i in range(n2)],
               "after_click_match_card_texts": [cards2.nth(i).inner_text()[:90].replace("\n", " | ") for i in range(n2)]})
    ok("after clicking #source-live: #thought-heading starts with 'Panic buying after a shortage rumour'", (heading2 or "").startswith("Panic buying after a shortage rumour"), f"heading={heading2!r} map_status_text={status2!r}")
    ok("after clicking #source-live: .match-card count == 4", n2 == 4, f"count={n2} classes={ev['after_click_match_card_classes']} texts={ev['after_click_match_card_texts']}")
    pg.screenshot(path=f"{OUT}/p6_live_own_thought.png", full_page=True)
    r, rv = call("resonance_update_consent", {"request_id": "pulse4-run2b-revoke", "shared": False})
    ok("resonance_update_consent {shared:false} -> revoked", not r.get("isError") and rv.get("revoked") is True, json.dumps({k: rv.get(k) for k in ("shared", "revoked", "discoverable")}))
    ev["console"] = console[:40]
    # --- OAuth consent page for a registered client named "Claude (custom connector)"
    req = urllib.request.Request(ORIGIN + "/oauth/register", data=json.dumps({"client_name": "Claude (custom connector)", "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
                                 "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"], "token_endpoint_auth_method": "none"}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp: client = json.loads(resp.read())
    cid = client["client_id"]; ev["consent_client_registered"] = bool(cid)
    import hashlib, base64, secrets
    ver = secrets.token_urlsafe(48); chal = base64.urlsafe_b64encode(hashlib.sha256(ver.encode()).digest()).rstrip(b"=").decode()
    from urllib.parse import urlencode
    url = ORIGIN + "/oauth/authorize?" + urlencode({"response_type": "code", "client_id": cid, "redirect_uri": "https://claude.ai/api/mcp/auth_callback", "code_challenge": chal, "code_challenge_method": "S256", "state": "pulse4", "scope": "resonance offline_access", "resource": ORIGIN + "/mcp"})
    pg2 = b.new_page(viewport={"width": 1200, "height": 900}); resp = pg2.goto(url, wait_until="networkidle", timeout=60000)
    body = pg2.inner_text("body"); radius = pg2.evaluate("() => { const m = document.querySelector('main.consent'); return m ? getComputedStyle(m).borderRadius : null; }")
    css_ok = pg2.evaluate("() => Array.from(document.styleSheets).map(s => s.href).filter(Boolean)")
    ev["consent"] = {"status": resp.status if resp else None, "client_name_shown": "Claude (custom connector)" in body, "main_consent_border_radius": radius, "stylesheets": css_ok, "title": pg2.title()}
    ok("consent page 200 and shows client name 'Claude (custom connector)'", resp and resp.status == 200 and "Claude (custom connector)" in body, f"status={resp.status if resp else None} title={pg2.title()!r}")
    ok("consent stylesheet applied: main.consent borderRadius == '22px'", radius == "22px", f"borderRadius={radius!r} stylesheets={css_ok}")
    pg2.screenshot(path=f"{OUT}/p6_consent.png", full_page=True)
    b.close()
ev["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
n = sum(c["ok"] for c in ev["checks"]); print(f"\n{n}/{len(ev['checks'])} checks passed")
s = json.dumps(ev, indent=1); assert (prev.get("confirmation_token") or "∅") not in s and cid not in s
open(f"{OUT}/browser/p6_run2b.json", "w").write(s)
