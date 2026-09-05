"""The production web server: real product state behind the browser WebMCP tools."""

from __future__ import annotations

import json
import threading
import unittest
from http.cookies import SimpleCookie
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.product.web_server import serve
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


FLOW_THOUGHT = {
    "topic": "Retry storm overloads a delivery queue",
    "domain": "distributed-systems",
    "nodes": [{"id": "n0", "label": "partial outage", "role": "problem"},
              {"id": "n1", "label": "synchronized retries", "role": "mechanism"},
              {"id": "n2", "label": "queue saturation", "role": "outcome"}],
    "relations": [{"source": "n0", "target": "n1", "type": "causes"},
                  {"source": "n1", "target": "n2", "type": "causes"}],
}


class WebServerWebMCPTests(unittest.TestCase):
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

    def test_root_serves_the_live_webmcp_transport(self):
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
        # The page cannot ask for anything but the visitor's own state: the
        # route that used to hand it a default source is gone along with the
        # fixture that source selected.
        with self.assertRaises(HTTPError) as ctx:
            urlopen(self.base + "/api/config", timeout=10)
        self.assertEqual(ctx.exception.code, 404)

    def test_discovery_without_a_shared_thought_is_409_not_500(self):
        # R16 Chrome audit: a fresh visitor used to get a 500 ("unexpected
        # product error") because the unshared case raised an unmapped
        # PermissionError. It is a product state, not a server fault.
        client = Client(self.base)
        client.guest()
        with self.assertRaises(HTTPError) as ctx:
            client.request("GET", "/api/discover")
        self.assertEqual(ctx.exception.code, 409)
        payload = json.loads(ctx.exception.read().decode())
        self.assertEqual(payload["error"], "share_required")
        self.assertIn("resonance_prepare_thought", payload["message"])

    def test_header_consent_pill_is_truthful_without_native_webmcp(self):
        # R17 acceptance finding (public-origin browser run): in a browser
        # without document.modelContext the page labelled a fresh,
        # never-shared guest "Shared with Resonance". The live module must
        # apply the visitor's authoritative consent state even when no agent
        # surface exists.
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
        for path in ("/api/context", "/api/discover"):
            with self.assertRaises(HTTPError) as ctx:
                client.request("GET", path)
            self.assertEqual(ctx.exception.code, 409, path)
            self.assertEqual(
                json.loads(ctx.exception.read().decode())["error"], "share_required", path)
        # The page renders that as its own state, never through the error path.
        self.assertIn('setShellState("unshared")', app)
        self.assertIn("function renderUnshared()", app)
        self.assertIn("clearActiveThought()", app)
        # There is no second source to fall back to any more: the fixture
        # thought is not reachable from the product at all.
        self.assertNotIn("thought-aria-plasma-lens", app)

    def test_index_is_served_in_the_state_it_will_settle_in(self):
        # Served at data-state="loading", the page painted the results dashboard
        # first — skeleton cards, "Resonance map", "Useful matches" — and only
        # then replaced it with the onboarding. A visitor saw the page change its
        # mind. The server knows the answer before any JavaScript runs.
        with urlopen(self.base + "/", timeout=10) as response:
            html = response.read().decode()
        self.assertIn('data-state="unshared"', html)      # no cookie: shared nothing
        self.assertNotIn('data-state="loading"', html)

        # once something IS shared, the dashboard is the right first paint
        client = Client(self.base)
        client.guest()
        thought = {"topic": "Initial paint check", "domain": "distributed-systems",
                   "nodes": [{"id": "n0", "label": "queue backlog", "role": "problem"},
                             {"id": "n1", "label": "synchronized retries", "role": "mechanism"},
                             {"id": "n2", "label": "amplified load", "role": "outcome"}],
                   "relations": [{"source": "n0", "target": "n1", "type": "causes"},
                                 {"source": "n1", "target": "n2", "type": "causes"}]}
        client.request("POST", "/api/webmcp/prepare", {"authorship": "their_own_words", "request_id": "paint-1", "thought": thought})
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
        # This page once had to admit the surfaces were separate accounts, because
        # the session cookie was SameSite=Strict and a browser navigating from
        # claude.ai to /oauth/authorize did not send it — so the consent page saw
        # no current account and every connection minted a new one. Real sign-in
        # plus a Lax session cookie fixed the cause, so the page may now say the
        # true thing. Both halves are pinned together: the promise on the page
        # and the cookie policy that makes it true.
        self.assertIn("the same account", html)
        self.assertNotIn("today they are not the same", html)
        from pathlib import Path as _Path
        server_src = (_Path(__file__).resolve().parents[1]
                      / "src" / "product" / "server.py").read_text(encoding="utf-8")
        self.assertIn("SameSite=Lax", server_src)
        self.assertNotIn("SameSite=Strict", server_src)
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

    def test_a_thought_shared_from_the_page_is_named_after_its_own_structure(self):
        """A share from this page arrives as text, so there is no topic to take
        from the caller, and every one of them was landing as "Shared thought"
        in the domain "general" — indistinguishable to the people they matched."""
        from src.product.web_server import _topic_from_structure
        client = Client(self.base)
        client.guest()
        client.request("POST", "/api/webmcp/prepare", {
            "authorship": "their_own_words",
            "request_id": "name-1",
            "context": ("Delivery pressure causes shortcuts. Shortcuts cause rework. "
                        "A protected slack week prevents shortcuts.")})
        _, preview, _ = client.request("GET", "/api/webmcp/preview")
        client.request("POST", "/api/webmcp/share", {
            "request_id": "name-2", "confirm": True,
            "confirmation_token": preview["confirmation_token"]})
        _, context, _ = client.request("GET", "/api/context")
        topic = (context.get("presentation") or {}).get("topic", "")
        self.assertNotEqual(topic, "Shared thought")
        self.assertIn("→", topic)
        # Derived from the structure the person already read and approved, so
        # naming it afterwards discloses nothing new.
        self.assertEqual(
            topic,
            _topic_from_structure(preview["will_become_discoverable"]["thought"])[:120])

    def test_naming_survives_a_thought_with_no_causal_spine(self):
        from src.product.web_server import _topic_from_structure
        self.assertEqual(_topic_from_structure({}), "")
        self.assertEqual(_topic_from_structure(None), "")
        self.assertEqual(
            _topic_from_structure({"nodes": [{"id": "a", "label": "one"},
                                             {"id": "b", "label": "two"}],
                                   "relations": []}),
            "one · two")

    def test_every_remote_tool_carries_the_annotations_directories_require(self):
        # Anthropic requires a `title` plus the applicable readOnlyHint /
        # destructiveHint. OpenAI requires readOnlyHint, openWorldHint AND
        # destructiveHint explicitly specified on every tool. "Explicitly"
        # means present, not merely defaulted.
        from src.product.mcp_bridge import TOOLS
        # A deliberate canary: adding a tool must be a conscious act, because a
        # tool that reaches a directory without these hints is a tool the host
        # cannot reason about. It caught the two standing-search tools, and then
        # the six shared-topic ones.
        self.assertEqual(len(TOOLS), 20)
        writes_visible_to_others = {
            "resonance_share_thought", "resonance_request_intro",
            "resonance_respond_intro", "resonance_send_message",
            "resonance_stop_sharing",
            # A shared topic is a place other people are looking at, so opening
            # one, contributing to it, and inviting or answering an invitation
            # all change what someone else can see. Reading it does not:
            # resonance_read_topic writes only this reader's own cursor, which
            # no other participant can observe.
            "resonance_open_topic", "resonance_contribute_to_topic",
            "resonance_invite_to_topic", "resonance_respond_topic_invite",
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

    def test_the_browser_surface_must_also_say_whose_reasoning_this_is(self):
        """The rule is not a rule if only one way in enforces it.

        An assistant driving the page through WebMCP is the same assistant that
        drives the MCP bridge, and it owes the same answer. It was asked on the
        bridge and not here, so anything the assistant framed itself could
        still be indexed under a person's name by going through the browser.
        """
        client = Client(self.base)
        client.guest()
        thought = {
            "topic": "Queue depth hides a slow consumer", "domain": "distributed-systems",
            "nodes": [
                {"id": "b0", "label": "slow consumer", "role": "problem"},
                {"id": "b1", "label": "growing queue depth", "role": "state"},
                {"id": "b2", "label": "delayed alerting", "role": "outcome"},
            ],
            "relations": [
                {"source": "b0", "target": "b1", "type": "causes"},
                {"source": "b1", "target": "b2", "type": "causes"},
            ],
        }
        for payload, why in (
            ({"request_id": "who-1", "thought": thought}, "authorship omitted"),
            ({"request_id": "who-2", "thought": thought,
              "authorship": "i_proposed_it"}, "the assistant's own framing"),
            ({"request_id": "who-3", "thought": thought,
              "authorship": "probably_theirs"}, "an invented value"),
        ):
            with self.subTest(why):
                with self.assertRaises(HTTPError) as caught:
                    client.request("POST", "/api/webmcp/prepare", payload)
                self.assertEqual(caught.exception.code, 400)

        _, prepared, _ = client.request(
            "POST", "/api/webmcp/prepare",
            {"request_id": "who-4", "thought": thought,
             "authorship": "their_words_reorganised"})
        self.assertFalse(prepared["discoverable"])

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
                                        {"authorship": "their_own_words", "request_id": "real-1", "thought": thought})
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
                                     {"authorship": "their_own_words", "request_id": "real-1", "thought": thought})
        self.assertEqual(again["draft_id"], prepared["draft_id"])
        with self.assertRaises(HTTPError) as ctx:
            client.request("POST", "/api/webmcp/prepare", {"authorship": "their_own_words", "request_id": "real-1", "context": "x"})
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
        client.request("POST", "/api/webmcp/prepare", {"authorship": "their_own_words", "request_id": "ctx-1", "thought": thought})
        _, preview, _ = client.request("GET", "/api/webmcp/preview")
        client.request("POST", "/api/webmcp/share", {"request_id": "ctx-2", "confirm": True,
                                                     "confirmation_token": preview["confirmation_token"]})
        _, live, _ = client.request("GET", "/api/context")
        self.assertEqual({n["label"] for n in live["active_thought"]["nodes"]},
                         {n["label"] for n in thought["nodes"]})
        self.assertEqual(live["presentation"]["topic"], "Panic buying after a shortage rumour")
        self.assertTrue(live["consent"]["shared_with_resonance"])
        with urlopen(self.base + "/app.mjs", timeout=10) as response:
            app = response.read().decode()
        self.assertIn('fetch("/api/context", {cache: "no-store"})', app)

    def test_webmcp_prepare_raw_context_and_invalid_thought(self):
        client = Client(self.base)
        client.guest()
        _, prepared, _ = client.request("POST", "/api/webmcp/prepare", {
            "authorship": "their_own_words",
            "request_id": "raw-1",
            "context": "A partial outage causes synchronized client retries. The retries cause "
                       "request amplification, which leads to cascading saturation. Jittered "
                       "backoff prevents the amplification."})
        self.assertFalse(prepared["discoverable"])
        self.assertEqual(prepared["input_kind"], "raw_text_fallback")
        self.assertEqual(prepared["source_retention"], "not_retained")
        with self.assertRaises(HTTPError) as ctx:
            client.request("POST", "/api/webmcp/prepare", {
                "authorship": "their_own_words",
                "request_id": "bad-1",
                "thought": {"nodes": [{"label": "a", "role": "vibe"}, {"label": "b", "role": "state"}],
                            "relations": []}})
        self.assertEqual(ctx.exception.code, 400)
        payload = json.loads(ctx.exception.read().decode())
        self.assertEqual(payload["error"], "validation_failed")
        self.assertIn("role must be one of", payload["message"])
        with self.assertRaises(HTTPError) as ctx:
            client.request("POST", "/api/webmcp/prepare",
                           {"authorship": "their_own_words", "request_id": "both-1", "context": "x", "thought": {"nodes": [], "relations": []}})
        self.assertEqual(ctx.exception.code, 400)
        # implicit prose: the accepted extractor abstains; the product must not
        # leave an empty shareable draft behind but tell the agent what to pass
        client = Client(self.base)
        client.guest()
        with self.assertRaises(HTTPError) as ctx:
            client.request("POST", "/api/webmcp/prepare", {
                "authorship": "their_own_words",
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
        _, one, _ = first.request("POST", "/api/webmcp/prepare", {"authorship": "their_own_words", "request_id": "same-1", "context": text})
        _, preview, _ = first.request("GET", "/api/webmcp/preview")
        first.request("POST", "/api/webmcp/share", {"request_id": "same-2", "confirm": True,
                                                    "confirmation_token": preview["confirmation_token"]})
        first.request("POST", "/api/webmcp/consent", {"request_id": "same-3", "shared": False})
        _, again, _ = first.request("POST", "/api/webmcp/prepare", {"authorship": "their_own_words", "request_id": "same-4", "context": text})
        self.assertNotEqual(again["draft_id"], one["draft_id"])
        second = Client(self.base); second.guest()
        _, other, _ = second.request("POST", "/api/webmcp/prepare", {"authorship": "their_own_words", "request_id": "same-1", "context": text})
        self.assertFalse(other["discoverable"])

    def test_webmcp_discover_before_share_is_409_share_required_not_500(self):
        # R17 acceptance finding: the first thing anyone does through the page
        # tools is a read; an unshared visitor must get a mapped product state
        # (409 share_required), not "unexpected product error".
        client = Client(self.base)
        client.guest()
        with self.assertRaises(HTTPError) as ctx:
            client.request("GET", "/api/webmcp/discover")
        self.assertEqual(ctx.exception.code, 409)
        payload = json.loads(ctx.exception.read().decode())
        self.assertEqual(payload["error"], "share_required")
        self.assertIn("resonance_prepare_thought", payload["message"])

    def test_webmcp_prepare_preview_share_live_discover_updates_same_product(self):
        client = Client(self.base)
        client.guest()

        _, prepared, _ = client.request("POST", "/api/webmcp/prepare", {
            "authorship": "their_own_words",
            "request_id": "flow-prepare-1", "thought": FLOW_THOUGHT,
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
            "request_id": "flow-share-1",
            "confirm": True,
            "confirmation_token": preview["confirmation_token"],
        })
        self.assertTrue(shared["shared"])
        self.assertTrue(shared["discoverable"])

        _, state, _ = client.request("GET", "/api/webmcp/state")
        self.assertFalse(state["draft_ready"])
        self.assertTrue(state["shared"])

        _, result, _ = client.request("GET", "/api/webmcp/discover")
        self.assertEqual(result["source"], "live")
        self.assertRegex(result["result_id"], r"^result-[0-9a-f]{24}$")
        self.assertGreater(len(result["matches_in_backend_order"]), 0)

        session_id = result["matches_in_backend_order"][0]["session_id"]
        _, evidence, _ = client.request(
            "GET", f"/api/webmcp/match?result_id={result['result_id']}"
                   f"&session_id={session_id}")
        self.assertEqual(evidence["source"], "live")
        self.assertEqual(evidence["match"]["session_id"], session_id)

        # The page reads the SAME live product result contract through its
        # presentation adapter, not a separate shadow state.
        _, visible, _ = client.request("GET", "/api/discover")
        self.assertEqual(visible["contract_version"], "resonance-discovery/0.1")
        self.assertGreater(len(visible["matches"]), 0)

    def test_prepare_without_the_person_s_own_reasoning_is_refused(self):
        # An empty prepare used to clone a fixture thought, so a visitor's first
        # durable row was a thought they had never had.
        client = Client(self.base)
        client.guest()
        with self.assertRaises(HTTPError) as ctx:
            client.request("POST", "/api/webmcp/prepare",
                           {"authorship": "their_own_words", "request_id": "empty-1", "note": "no content"})
        self.assertEqual(ctx.exception.code, 400)
        payload = json.loads(ctx.exception.read().decode())
        self.assertEqual(payload["error"], "validation_failed")
        with self.assertRaises(HTTPError) as ctx:
            client.request("GET", "/api/webmcp/preview")
        self.assertEqual(ctx.exception.code, 409)  # no draft was created

    def test_webmcp_operation_receipt_reconciles_same_process_retry(self):
        client = Client(self.base)
        client.guest()
        body = {"authorship": "their_own_words", "request_id": "idempotent-prepare", "thought": FLOW_THOUGHT}
        _, first, _ = client.request("POST", "/api/webmcp/prepare", body)
        _, second, _ = client.request("POST", "/api/webmcp/prepare", body)
        self.assertEqual(first, second)
        _, op, _ = client.request(
            "GET", "/api/webmcp/operation?operation=prepare"
                   "&request_id=idempotent-prepare")
        self.assertTrue(op["committed"])
        self.assertEqual(op["result"], first)


    def test_the_browser_surface_answers_in_words_too(self):
        """An assistant driving the page is as much in a conversation as one
        driving the chat connector, and it was handed a bare object to render.

        The sentence comes from the same module the MCP bridge uses, so the
        two surfaces cannot drift into describing one result differently.
        """
        client = Client(self.base)
        client.guest()
        thought = {
            "topic": "Slow consumer hides behind queue depth",
            "domain": "distributed-systems",
            "nodes": [
                {"id": "c0", "label": "slow consumer", "role": "problem"},
                {"id": "c1", "label": "growing queue depth", "role": "state"},
                {"id": "c2", "label": "delayed alerting", "role": "outcome"},
            ],
            "relations": [
                {"source": "c0", "target": "c1", "type": "causes"},
                {"source": "c1", "target": "c2", "type": "causes"},
            ],
        }
        _, prepared, _ = client.request("POST", "/api/webmcp/prepare", {
            "authorship": "their_own_words", "request_id": "say-1",
            "thought": thought})
        said = prepared.get("say")
        self.assertTrue(said, prepared)
        self.assertFalse(said.lstrip().startswith("{"), said)
        self.assertNotIn("contract_version", said)
        # Everything that was on the wire before is still on it.
        self.assertFalse(prepared["discoverable"])
        self.assertEqual(prepared["source_retention"], "not_retained")

        _, preview, _ = client.request("GET", "/api/webmcp/preview")
        _, shared, _ = client.request("POST", "/api/webmcp/share", {
            "request_id": "say-2", "confirm": True,
            "confirmation_token": preview["confirmation_token"]})
        self.assertTrue(shared["discoverable"])
        self.assertIn("discoverable", shared["say"])
        self.assertNotIn("session_id", shared["say"])

if __name__ == "__main__":
    unittest.main()
