"""Competition browser bridge: real R13/R14 product state behind R10 WebMCP UX."""

from __future__ import annotations

import json
import threading
import unittest
from http.cookies import SimpleCookie
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.product.competition_server import serve
from src.product.server import build_runtime


class Client:
    def __init__(self, base: str):
        self.base = base
        self.cookie = None
        self.csrf = None

    def request(self, method: str, path: str, body=None):
        headers = {"Content-Type": "application/json", "Origin": self.base}
        if self.cookie:
            headers["Cookie"] = self.cookie
        if self.csrf:
            headers["X-Resonance-CSRF"] = self.csrf
        data = json.dumps(body).encode() if body is not None else None
        req = Request(self.base + path, data=data, headers=headers, method=method)
        with urlopen(req, timeout=15) as response:
            set_cookie = response.headers.get("Set-Cookie")
            if set_cookie:
                morsel = SimpleCookie(set_cookie).get("resonance_token")
                if morsel is not None:
                    self.cookie = f"resonance_token={morsel.value}"
            return response.status, json.loads(response.read().decode()), dict(response.headers)

    def guest(self):
        _, payload, _ = self.request("POST", "/api/product/guest", {})
        self.csrf = payload["csrf_token"]
        return payload


class CompetitionWebMCPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pending = build_runtime(":memory:", allowed_origins=frozenset({"pending"}))
        server = serve("127.0.0.1", 0, runtime=pending)
        host, port = server.server_address[:2]
        cls.base = f"http://{host}:{port}"
        runtime = build_runtime(":memory:", allowed_origins=frozenset({cls.base}))
        server.RequestHandlerClass.runtime = runtime
        cls.runtime = runtime
        cls.server = server
        cls.thread = threading.Thread(target=server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_root_serves_live_webmcp_transport_but_replay_starts_explicit(self):
        with urlopen(self.base + "/", timeout=10) as response:
            html = response.read().decode()
            self.assertIn('src="/webmcp.mjs"', html)
            self.assertEqual(response.headers.get("Permissions-Policy"), "tools=(self)")
        with urlopen(self.base + "/webmcp.mjs", timeout=10) as response:
            source = response.read().decode()
        self.assertIn("document.modelContext", source)
        self.assertIn('from "/session.mjs"', source)
        self.assertIn("apiFetch", source)
        self.assertNotIn("STATE =", source)
        with urlopen(self.base + "/api/config", timeout=10) as response:
            config = json.loads(response.read())
        # The public origin must open on the visitor's own state. Defaulting to
        # "replay" made every first load render the four fixture personas from
        # src/discovery/fixtures/example_response.json as if they were people in
        # the live corpus.
        self.assertEqual(config["default_source"], "live")
        self.assertTrue(config["live_product"])

    def test_live_source_without_shared_thought_is_409_not_500(self):
        # R16 Chrome audit: a fresh visitor clicking "Live MCP" used to get a
        # 500 ("unexpected product error") because the unshared case raised an
        # unmapped PermissionError. It is a product state, not a server fault.
        client = Client(self.base)
        client.guest()
        with self.assertRaises(HTTPError) as ctx:
            client.request("GET", "/api/discover?source=live")
        self.assertEqual(ctx.exception.code, 409)
        payload = json.loads(ctx.exception.read().decode())
        self.assertEqual(payload["error"], "share_required")
        self.assertIn("resonance_prepare_thought", payload["message"])

    def test_header_consent_pill_is_truthful_without_native_webmcp(self):
        # R17 acceptance finding (public-origin browser run): in a browser
        # without document.modelContext the R9 replay narrative labelled a
        # fresh, never-shared guest "Shared with Resonance". The live module
        # must apply the visitor's authoritative consent state even when no
        # agent surface exists, and the replay narrative must yield on the
        # live product.
        with urlopen(self.base + "/webmcp.mjs", timeout=10) as response:
            live = response.read().decode()
        unavailable = live.index('setStatus("WebMCP · unavailable")')
        self.assertIn("applyAuthoritativeState(await readAuthoritativeState())",
                      live[unavailable:unavailable + 600])
        with urlopen(self.base + "/app.mjs", timeout=10) as response:
            app = response.read().decode()
        shared = app.index('el("span", "", "Shared with Resonance")')
        self.assertIn('window.__resonanceWebMCP?.mode !== "live-product"', app[shared - 400:shared])

    def test_webmcp_pill_reports_the_browser_not_the_consent_state(self):
        # Regression for the fix above. Making the header consent pill truthful
        # also routed applyAuthoritativeState() through the WebMCP *capability*
        # pill, so a browser with no document.modelContext showed
        # "WebMCP · private" — byte-identical to a browser where registration
        # succeeded. Observed on the public origin in Chrome 152 (stock).
        # Card A step 1 asks a tester to stop when the pill says "unavailable",
        # so this pill has to keep saying it.
        with urlopen(self.base + "/webmcp.mjs", timeout=10) as response:
            live = response.read().decode()
        unavailable = live.index('setStatus("WebMCP · unavailable")')
        # the capability is recorded before the status is written …
        self.assertIn("agentSurface = false", live[unavailable - 200:unavailable])
        # … and the consent updater must not write the capability pill then.
        apply_at = live.index("function applyAuthoritativeState")
        # Window sized for the function plus its comments, which carry the
        # reasoning for both the capability guard and the consent event. What
        # is asserted below is the ORDER of three statements inside it, not
        # their distance from the top.
        body = live[apply_at:apply_at + 2200]
        self.assertIn("if (agentSurface === false) return;", body)
        self.assertLess(body.index("if (agentSurface === false) return;"),
                        body.index('setStatus("WebMCP · LIVE shared")'))
        # setConsentVisible still runs first: the header keeps telling the truth.
        self.assertLess(body.index("setConsentVisible(state.shared === true)"),
                        body.index("if (agentSurface === false) return;"))

    def test_landing_page_of_a_fresh_visitor_has_no_fixture_personas(self):
        # The product opens on the visitor's own state. Nothing a first-time
        # visitor is served may carry the fixture personas from
        # src/discovery/fixtures/example_response.json.
        client = Client(self.base)
        client.guest()
        with urlopen(self.base + "/", timeout=10) as response:
            html = response.read().decode()
        with urlopen(self.base + "/app.mjs", timeout=10) as response:
            app = response.read().decode()
        personas = ["Kwame A.", "Noah R.", "Mei L.", "Gabe S.", "Camille B.",
                    "Diego R.", "Sam D.", "Sora N.", "Theo M.", "Yuki T."]
        for name in personas:
            self.assertNotIn(name, html)
            self.assertNotIn(name, app)
        self.assertNotIn("aria-plasma-lens", html)
        # Both data routes the default view touches fail closed for this visitor.
        for path in ("/api/context", "/api/discover?source=live"):
            with self.assertRaises(HTTPError) as ctx:
                client.request("GET", path)
            self.assertEqual(ctx.exception.code, 409, path)
            self.assertEqual(
                json.loads(ctx.exception.read().decode())["error"], "share_required", path)
        # The page renders that as its own state, never through the error path.
        self.assertIn('dataset.state = "unshared"', app)
        self.assertIn("function renderUnshared()", app)
        self.assertIn("clearActiveThought()", app)
        # Replay stays reachable and stays labelled as example data.
        _, replay_context, _ = client.request("GET", "/api/context?source=replay")
        self.assertEqual(replay_context["active_thought"]["thought_id"],
                         "thought-aria-plasma-lens")
        self.assertIn("example personas, not real participants", app)

    def test_index_is_served_in_the_state_it_will_settle_in(self):
        # Served at data-state="loading", the page painted the results dashboard
        # first — skeleton cards, "Resonance map", "Useful matches" — and only
        # then replaced it with the onboarding. A visitor saw the page change its
        # mind. The server knows the answer before any JavaScript runs.
        with urlopen(self.base + "/", timeout=10) as response:
            html = response.read().decode()
        self.assertIn('data-state="unshared"', html)      # no cookie: shared nothing
        self.assertNotIn('data-state="loading"', html)
        # asking for the fixture explicitly keeps the neutral loading state
        with urlopen(self.base + "/?source=replay", timeout=10) as response:
            self.assertIn('data-state="loading"', response.read().decode())

        # once something IS shared, the dashboard is the right first paint
        client = Client(self.base)
        client.guest()
        thought = {"topic": "Initial paint check", "domain": "distributed-systems",
                   "nodes": [{"id": "n0", "label": "queue backlog", "role": "problem"},
                             {"id": "n1", "label": "synchronized retries", "role": "mechanism"},
                             {"id": "n2", "label": "amplified load", "role": "outcome"}],
                   "relations": [{"source": "n0", "target": "n1", "type": "causes"},
                                 {"source": "n1", "target": "n2", "type": "causes"}]}
        client.request("POST", "/api/webmcp/prepare", {"request_id": "paint-1", "thought": thought})
        _, preview, _ = client.request("GET", "/api/webmcp/preview")
        client.request("POST", "/api/webmcp/share", {"request_id": "paint-2", "confirm": True,
                                                     "confirmation_token": preview["confirmation_token"]})
        request = Request(self.base + "/", headers={"Cookie": client.cookie})
        with urlopen(request, timeout=10) as response:
            self.assertIn('data-state="loading"', response.read().decode())

    def test_the_page_says_the_product_speaks_both_transports(self):
        # The "This browser" card used to read "there is nothing to register
        # here", which describes the browser but sounds like the product has no
        # WebMCP. Resonance speaks both, and the OAuth consent page already
        # offers "Continue as your current account" so they can be one account —
        # the page never said so.
        with urlopen(self.base + "/", timeout=10) as response:
            html = response.read().decode()
        self.assertIn("Resonance also speaks WebMCP", html)
        # The page used to claim the two surfaces could be one account via the
        # consent screen's "Continue as your current account". That option cannot
        # appear in the flow it exists for: the session cookie is SameSite=Strict,
        # so a browser navigating from claude.ai to /oauth/authorize does not send
        # it, and the consent page sees no current account. Until identity is
        # fixed, the page must say what is true.
        self.assertIn("today they are not the same", html)
        self.assertNotIn("preselects it", html)
        with urlopen(self.base + "/app.mjs", timeout=10) as response:
            app = response.read().decode()
        # both branches describe the BROWSER, and neither denies the capability
        self.assertIn("Resonance also speaks WebMCP, and this browser has it", app)
        self.assertIn("but this browser does not expose", app)
        self.assertNotIn("there is nothing to register here.", app)
        # The page promises the consent screen offers that option; keep the two
        # in step, so the promise cannot outlive the behaviour. (This runtime has
        # no OAuth core attached, so assert against the core that serves it.)
        from pathlib import Path
        oauth_src = (Path(__file__).resolve().parents[1]
                     / "src" / "remote" / "oauth.py").read_text(encoding="utf-8")
        self.assertIn("Continue as your current account", oauth_src)
        self.assertIn('value="current" checked', oauth_src)

    def test_directory_listing_prerequisites_are_served(self):
        # A connector directory will not list a server without these. Anthropic
        # rejects a submission outright when the privacy policy is missing, and
        # OpenAI's form requires website, support, privacy and terms URLs that
        # "match the publisher and disclose relevant data handling". Serving
        # them from this origin means the URL a reviewer checks is the URL the
        # tools actually run on.
        for path in ("/privacy", "/terms", "/support"):
            with urlopen(self.base + path, timeout=10) as response:
                self.assertEqual(response.status, 200, path)
                self.assertTrue(response.headers.get("Content-Type", "").startswith("text/html"), path)
                body = response.read().decode()
            self.assertIn("/legal.css", body, path)
            self.assertNotIn("__RESONANCE_", body, f"{path} left a placeholder unsubstituted")
        with urlopen(self.base + "/legal.css", timeout=10) as response:
            self.assertEqual(response.status, 200)

        # The privacy page has to state the things the policy is judged on.
        with urlopen(self.base + "/privacy", timeout=10) as response:
            privacy = response.read().decode()
        for claim in ("What is stored", "What is not stored", "Retention and removal",
                      "Who can see what", "Contact"):
            self.assertIn(claim, privacy)
        # …and the load-bearing factual claim, which the code must keep true.
        self.assertIn("not stored", privacy)

        # Unconfigured, the contact says so rather than showing a plausible
        # address nobody reads.
        self.assertIn("not configured on this deployment", privacy)

    def test_openai_domain_challenge_is_a_bare_token_or_absent(self):
        # OpenAI verifies control of the hosting domain by fetching a token it
        # hands the publisher. Its spec is explicit: return ONLY the token — not
        # JSON, not a list. Unconfigured it must 404, so a half-configured
        # deployment cannot look verified.
        with self.assertRaises(HTTPError) as ctx:
            urlopen(self.base + "/.well-known/openai-apps-challenge", timeout=10)
        self.assertEqual(ctx.exception.code, 404)

        import os as _os
        from src.product import server as product_server
        previous = _os.environ.get("RESONANCE_OPENAI_CHALLENGE")
        _os.environ["RESONANCE_OPENAI_CHALLENGE"] = "tok-en_value.123"
        try:
            with urlopen(self.base + "/.well-known/openai-apps-challenge", timeout=10) as response:
                self.assertEqual(response.status, 200)
                self.assertTrue(response.headers.get("Content-Type", "").startswith("text/plain"))
                self.assertEqual(response.read(), b"tok-en_value.123")   # bare, no newline
        finally:
            if previous is None:
                _os.environ.pop("RESONANCE_OPENAI_CHALLENGE", None)
            else:
                _os.environ["RESONANCE_OPENAI_CHALLENGE"] = previous
        self.assertIsNotNone(product_server)

    def test_every_remote_tool_carries_the_annotations_directories_require(self):
        # Anthropic requires a `title` plus the applicable readOnlyHint /
        # destructiveHint. OpenAI requires readOnlyHint, openWorldHint AND
        # destructiveHint explicitly specified on every tool. "Explicitly"
        # means present, not merely defaulted.
        from src.product.mcp_bridge import TOOLS
        # A deliberate canary: adding a tool must be a conscious act, because a
        # tool that reaches a directory without these hints is a tool the host
        # cannot reason about. It caught the two standing-search tools.
        self.assertEqual(len(TOOLS), 14)
        writes_visible_to_others = {
            "resonance_share_thought", "resonance_request_intro",
            "resonance_respond_intro", "resonance_send_message",
            "resonance_stop_sharing",
        }
        for tool in TOOLS:
            name = tool["name"]
            self.assertTrue(tool.get("title"), name)
            ann = tool["annotations"]
            for hint in ("readOnlyHint", "destructiveHint", "openWorldHint"):
                self.assertIn(hint, ann, f"{name} is missing {hint}")
                self.assertIsInstance(ann[hint], bool, f"{name}.{hint}")
            # a read-only tool cannot be destructive or change what others see
            if ann["readOnlyHint"]:
                self.assertFalse(ann["destructiveHint"], name)
                self.assertFalse(ann["openWorldHint"], name)
            # openWorldHint means "changes state other people can see"
            self.assertEqual(ann["openWorldHint"], name in writes_visible_to_others, name)
        # only stop_sharing revokes something
        destructive = {t["name"] for t in TOOLS if t["annotations"]["destructiveHint"]}
        self.assertEqual(destructive, {"resonance_stop_sharing"})

    def test_webmcp_prepare_accepts_the_agents_real_thought(self):
        # Post-release product gap: the browser prepare used to clone the page's
        # flagship thought; an agent must be able to hand over the person's REAL
        # reasoning (structured graph or raw text), same contract as remote MCP.
        client = Client(self.base)
        client.guest()
        thought = {
            "topic": "Retry storm after a partial outage", "domain": "distributed-systems",
            "nodes": [
                {"id": "a0", "label": "partial upstream outage", "role": "problem"},
                {"id": "a1", "label": "synchronized client retries", "role": "mechanism"},
                {"id": "a2", "label": "request amplification", "role": "state"},
                {"id": "a3", "label": "jittered exponential backoff", "role": "method"},
            ],
            "relations": [
                {"source": "a0", "target": "a1", "type": "causes"},
                {"source": "a1", "target": "a2", "type": "causes"},
                {"source": "a3", "target": "a2", "type": "prevents"},
            ],
        }
        _, prepared, _ = client.request("POST", "/api/webmcp/prepare",
                                        {"request_id": "real-1", "thought": thought})
        self.assertFalse(prepared["discoverable"])
        self.assertEqual(prepared["input_kind"], "agent_structured")
        self.assertEqual(prepared["source_retention"], "not_retained")
        _, preview, _ = client.request("GET", "/api/webmcp/preview")
        labels = {n["label"] for n in preview["will_become_discoverable"]["thought"]["nodes"]}
        self.assertEqual(labels, {n["label"] for n in thought["nodes"]})
        self.assertEqual(preview["will_become_discoverable"]["presentation"]["topic"],
                         "Retry storm after a partial outage")
        self.assertEqual(preview["will_become_discoverable"]["presentation"]["domain"],
                         "distributed-systems")
        # same request_id + same input replays; different input conflicts
        _, again, _ = client.request("POST", "/api/webmcp/prepare",
                                     {"request_id": "real-1", "thought": thought})
        self.assertEqual(again["draft_id"], prepared["draft_id"])
        with self.assertRaises(HTTPError) as ctx:
            client.request("POST", "/api/webmcp/prepare", {"request_id": "real-1", "context": "x"})
        self.assertEqual(ctx.exception.code, 409)

    def test_context_follows_the_source_after_a_real_share(self):
        # The R9 page's active-thought panel used to keep the fixture thought
        # after the visitor shared their own; /api/context now follows the
        # source and app.mjs re-renders it on every source switch.
        client = Client(self.base)
        client.guest()
        # Before sharing, the visitor has no active thought. This used to hand
        # back the fixture thought (`thought-aria-plasma-lens`) as if it were
        # theirs; it now fails closed the same way discovery does.
        with self.assertRaises(HTTPError) as ctx:
            client.request("GET", "/api/context?source=live")
        self.assertEqual(ctx.exception.code, 409)
        self.assertEqual(json.loads(ctx.exception.read().decode())["error"], "share_required")
        with self.assertRaises(HTTPError) as ctx:
            client.request("GET", "/api/context")
        self.assertEqual(ctx.exception.code, 409)
        thought = {"topic": "Panic buying after a shortage rumour", "domain": "consumer-economics",
                   "nodes": [{"id": "b0", "label": "supply shortage rumour", "role": "problem"},
                             {"id": "b1", "label": "synchronized bulk purchases", "role": "mechanism"},
                             {"id": "b2", "label": "empty shelves", "role": "outcome"}],
                   "relations": [{"source": "b0", "target": "b1", "type": "causes"},
                                 {"source": "b1", "target": "b2", "type": "causes"}]}
        client.request("POST", "/api/webmcp/prepare", {"request_id": "ctx-1", "thought": thought})
        _, preview, _ = client.request("GET", "/api/webmcp/preview")
        client.request("POST", "/api/webmcp/share", {"request_id": "ctx-2", "confirm": True,
                                                     "confirmation_token": preview["confirmation_token"]})
        _, live, _ = client.request("GET", "/api/context?source=live")
        self.assertEqual({n["label"] for n in live["active_thought"]["nodes"]},
                         {n["label"] for n in thought["nodes"]})
        self.assertEqual(live["presentation"]["topic"], "Panic buying after a shortage rumour")
        self.assertTrue(live["consent"]["shared_with_resonance"])
        _, replay, _ = client.request("GET", "/api/context?source=replay")
        self.assertEqual(replay["active_thought"]["thought_id"], "thought-aria-plasma-lens")
        with self.assertRaises(HTTPError) as ctx:
            client.request("GET", "/api/context?source=nope")
        self.assertEqual(ctx.exception.code, 400)
        with urlopen(self.base + "/app.mjs", timeout=10) as response:
            app = response.read().decode()
        self.assertIn("fetch(`/api/context?source=${encodeURIComponent(source)}`", app)

    def test_webmcp_prepare_raw_context_and_invalid_thought(self):
        client = Client(self.base)
        client.guest()
        _, prepared, _ = client.request("POST", "/api/webmcp/prepare", {
            "request_id": "raw-1",
            "context": "A partial outage causes synchronized client retries. The retries cause "
                       "request amplification, which leads to cascading saturation. Jittered "
                       "backoff prevents the amplification."})
        self.assertFalse(prepared["discoverable"])
        self.assertEqual(prepared["input_kind"], "raw_text_fallback")
        self.assertEqual(prepared["source_retention"], "not_retained")
        with self.assertRaises(HTTPError) as ctx:
            client.request("POST", "/api/webmcp/prepare", {
                "request_id": "bad-1",
                "thought": {"nodes": [{"label": "a", "role": "vibe"}, {"label": "b", "role": "state"}],
                            "relations": []}})
        self.assertEqual(ctx.exception.code, 400)
        payload = json.loads(ctx.exception.read().decode())
        self.assertEqual(payload["error"], "validation_failed")
        self.assertIn("role must be one of", payload["message"])
        with self.assertRaises(HTTPError) as ctx:
            client.request("POST", "/api/webmcp/prepare",
                           {"request_id": "both-1", "context": "x", "thought": {"nodes": [], "relations": []}})
        self.assertEqual(ctx.exception.code, 400)
        # implicit prose: the accepted extractor abstains; the product must not
        # leave an empty shareable draft behind but tell the agent what to pass
        client = Client(self.base)
        client.guest()
        with self.assertRaises(HTTPError) as ctx:
            client.request("POST", "/api/webmcp/prepare", {
                "request_id": "implicit-1",
                "context": "The upstream was slow all week. Thousands of clients noticed timeouts. "
                           "The whole tier ended up saturated by Friday."})
        self.assertEqual(ctx.exception.code, 400)
        payload = json.loads(ctx.exception.read().decode())
        self.assertEqual(payload["error"], "validation_failed")
        self.assertIn("call again with `thought`", payload["message"])
        with self.assertRaises(HTTPError) as ctx:
            client.request("GET", "/api/webmcp/preview")
        self.assertEqual(ctx.exception.code, 409)  # no private draft left behind

    def test_same_raw_text_can_be_prepared_again_and_by_another_person(self):
        # The extracted Thought DNA id is namespaced per person and attempt, so
        # re-preparing the same sentences (after stop-sharing) or another
        # visitor preparing them does not hit "thought_id is already reserved".
        text = ("A partial outage causes synchronized client retries. The retries cause "
                "request amplification, which leads to cascading saturation.")
        first = Client(self.base); first.guest()
        _, one, _ = first.request("POST", "/api/webmcp/prepare", {"request_id": "same-1", "context": text})
        _, preview, _ = first.request("GET", "/api/webmcp/preview")
        first.request("POST", "/api/webmcp/share", {"request_id": "same-2", "confirm": True,
                                                    "confirmation_token": preview["confirmation_token"]})
        first.request("POST", "/api/webmcp/consent", {"request_id": "same-3", "shared": False})
        _, again, _ = first.request("POST", "/api/webmcp/prepare", {"request_id": "same-4", "context": text})
        self.assertNotEqual(again["draft_id"], one["draft_id"])
        second = Client(self.base); second.guest()
        _, other, _ = second.request("POST", "/api/webmcp/prepare", {"request_id": "same-1", "context": text})
        self.assertFalse(other["discoverable"])

    def test_webmcp_discover_before_share_is_409_share_required_not_500(self):
        # R17 acceptance finding: the first thing a judge does on the card is a
        # read through the page tool; an unshared visitor must get a mapped
        # product state (409 share_required), not "unexpected product error".
        client = Client(self.base)
        client.guest()
        for source in ("replay", "live"):
            with self.assertRaises(HTTPError) as ctx:
                client.request("GET", f"/api/webmcp/discover?source={source}")
            self.assertEqual(ctx.exception.code, 409, source)
            payload = json.loads(ctx.exception.read().decode())
            self.assertEqual(payload["error"], "share_required")
            self.assertIn("resonance_prepare_thought", payload["message"])

    def test_webmcp_prepare_preview_share_live_discover_updates_same_product(self):
        client = Client(self.base)
        client.guest()

        _, prepared, _ = client.request("POST", "/api/webmcp/prepare", {
            "request_id": "competition-prepare-1", "note": "judge flow",
        })
        self.assertFalse(prepared["discoverable"])
        self.assertTrue(prepared["session_id"].startswith("ses-"))

        _, state, _ = client.request("GET", "/api/webmcp/state")
        self.assertTrue(state["draft_ready"])
        self.assertFalse(state["shared"])

        _, preview, _ = client.request("GET", "/api/webmcp/preview")
        self.assertEqual(preview["draft_id"], prepared["draft_id"])
        self.assertTrue(preview["requires_explicit_confirmation"])
        self.assertTrue(preview["confirmation_token"])
        self.assertIn("thought", preview["will_become_discoverable"])

        _, shared, _ = client.request("POST", "/api/webmcp/share", {
            "request_id": "competition-share-1",
            "confirm": True,
            "confirmation_token": preview["confirmation_token"],
        })
        self.assertTrue(shared["shared"])
        self.assertTrue(shared["discoverable"])

        _, state, _ = client.request("GET", "/api/webmcp/state")
        self.assertFalse(state["draft_ready"])
        self.assertTrue(state["shared"])

        _, result, _ = client.request("GET", "/api/webmcp/discover?source=live")
        self.assertEqual(result["source"], "live")
        self.assertRegex(result["result_id"], r"^result-[0-9a-f]{24}$")
        self.assertGreater(len(result["matches_in_backend_order"]), 0)

        session_id = result["matches_in_backend_order"][0]["session_id"]
        _, evidence, _ = client.request(
            "GET", f"/api/webmcp/match?result_id={result['result_id']}"
                   f"&session_id={session_id}")
        self.assertEqual(evidence["source"], "live")
        self.assertEqual(evidence["match"]["session_id"], session_id)

        # The unchanged R9 page source switch reads the SAME live product result
        # contract through its presentation adapter, not legacy stdio shadow state.
        _, visible, _ = client.request("GET", "/api/discover?source=live")
        self.assertEqual(visible["contract_version"], "resonance-discovery/0.1")
        self.assertGreater(len(visible["matches"]), 0)

    def test_webmcp_operation_receipt_reconciles_same_process_retry(self):
        client = Client(self.base)
        client.guest()
        body = {"request_id": "competition-idempotent-prepare", "note": "once"}
        _, first, _ = client.request("POST", "/api/webmcp/prepare", body)
        _, second, _ = client.request("POST", "/api/webmcp/prepare", body)
        self.assertEqual(first, second)
        _, op, _ = client.request(
            "GET", "/api/webmcp/operation?operation=prepare"
                   "&request_id=competition-idempotent-prepare")
        self.assertTrue(op["committed"])
        self.assertEqual(op["result"], first)


if __name__ == "__main__":
    unittest.main()
