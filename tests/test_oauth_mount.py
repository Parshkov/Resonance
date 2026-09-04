"""R15C production mount (#136): issuer derivation behind the Railway proxy,
RFC 9728 challenge on unauthenticated /mcp, and dispatch of the well-known /
oauth paths to whatever OAuth core the runtime carries (none today -> 404).
No OAuth protocol semantics are tested here; that is R15A/R15B (#134/#135)."""

from __future__ import annotations

import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.product import oauth_mount as om
from src.product.server import build_runtime, serve


class IssuerDerivationTests(unittest.TestCase):
    def test_single_https_allowed_origin_wins_over_proxy_headers(self):
        issuer = om.public_issuer(
            frozenset({"https://resonance-production-cfe3.up.railway.app"}),
            {"Host": "0.0.0.0:8080", "X-Forwarded-Proto": "https",
             "X-Forwarded-Host": "other.example"})
        self.assertEqual(issuer, "https://resonance-production-cfe3.up.railway.app")
        self.assertEqual(om.resource_url(issuer),
                         "https://resonance-production-cfe3.up.railway.app/mcp")
        self.assertEqual(om.resource_metadata_url(issuer),
                         "https://resonance-production-cfe3.up.railway.app"
                         "/.well-known/oauth-protected-resource")

    def test_headers_are_trusted_only_when_they_name_an_allowed_origin(self):
        # A caller-controlled Host/X-Forwarded-Host must never become the
        # issuer (metadata poisoning); it is used only if it is allowed itself.
        self.assertEqual(
            om.public_issuer(frozenset({"http://127.0.0.1:8788"}),
                             {"Host": "0.0.0.0:8080", "X-Forwarded-Proto": "https",
                              "X-Forwarded-Host": "app.example"}),
            "http://127.0.0.1:8788")
        self.assertEqual(
            om.public_issuer(frozenset({"https://a.example", "https://b.example"}),
                             {"Host": "b.example", "X-Forwarded-Proto": "https"}),
            "https://b.example")
        self.assertEqual(
            om.public_issuer(frozenset({"https://a.example", "https://b.example"}),
                             {"Host": "evil.example", "X-Forwarded-Proto": "https"}),
            "https://a.example")
        # no allowlist at all (local development): Host is all there is
        self.assertEqual(om.public_issuer(frozenset(), {"Host": "127.0.0.1:9"}),
                         "http://127.0.0.1:9")
        # local http origin and no headers at all -> the allowed origin itself
        self.assertEqual(om.public_issuer(frozenset({"http://127.0.0.1:8788"}), {}),
                         "http://127.0.0.1:8788")

    def test_canonical_origin_is_the_first_declared_not_the_alphabetical_one(self):
        # A deployment that serves a custom domain alongside the platform host
        # has two allowed origins. `allowed_origins` is a set, so it cannot say
        # which is canonical, and public_issuer() without headers falls back to
        # the alphabetically first https origin — here the platform host, which
        # is exactly the wrong answer once a custom domain exists.
        declared = ["https://resonance.parshkov.com",
                    "https://resonance-production-cfe3.up.railway.app"]
        allowed = frozenset(declared)
        self.assertEqual(om.public_issuer(allowed),
                         "https://resonance-production-cfe3.up.railway.app")
        self.assertEqual(om.canonical_origin(declared, allowed),
                         "https://resonance.parshkov.com")
        # Per request each allowed host still serves its own metadata, so the
        # legacy platform URL keeps working for clients already registered on it.
        for host in ("resonance.parshkov.com", "resonance-production-cfe3.up.railway.app"):
            self.assertEqual(
                om.public_issuer(allowed, {"X-Forwarded-Host": host,
                                           "X-Forwarded-Proto": "https"}),
                f"https://{host}")
        # Trailing slashes and blanks in the operator's argv are tolerated …
        self.assertEqual(
            om.canonical_origin(["", "  https://resonance.parshkov.com/ "], allowed),
            "https://resonance.parshkov.com")
        # … and with nothing declared it degrades to the old behaviour.
        self.assertEqual(om.canonical_origin(None, allowed), om.public_issuer(allowed))
        self.assertEqual(om.canonical_origin([], allowed), om.public_issuer(allowed))

    def test_challenge_points_at_protected_resource_metadata(self):
        value = om.www_authenticate("https://x.example")
        self.assertTrue(value.startswith("Bearer "))
        self.assertIn('resource_metadata="https://x.example/.well-known/oauth-protected-resource"', value)
        self.assertIn('error="invalid_token"', om.www_authenticate("https://x.example", error="invalid_token"))

    def test_dispatch_without_core_is_404_and_bearer_passthrough(self):
        resp = om.dispatch(None, method="GET", path=om.AUTH_SERVER_PATH, query={},
                           headers={}, body=b"", issuer="https://x.example")
        self.assertEqual(resp.status, 404)
        self.assertEqual(om.resolve_bearer(None, "tok", issuer="https://x.example"), "tok")
        self.assertIsNone(om.resolve_bearer(None, "", issuer="https://x.example"))

    def test_dispatch_with_core_forwards_issuer_and_returns_triple(self):
        seen = {}

        class Core:
            def handle(self, method, path, query, headers, body, *, issuer):
                seen.update(method=method, path=path, issuer=issuer, q=query)
                return 200, {"Content-Type": "application/json"}, json.dumps({"issuer": issuer})

            def resolve_bearer(self, token, *, resource):
                seen["resource"] = resource
                return "r12-" + token if token == "good" else None

        resp = om.dispatch(Core(), method="GET", path=om.AUTH_SERVER_PATH, query={"a": ["1"]},
                           headers={}, body=b"", issuer="https://x.example")
        self.assertEqual((resp.status, json.loads(resp.body)["issuer"]), (200, "https://x.example"))
        self.assertEqual(seen["q"], {"a": ["1"]})
        self.assertEqual(om.resolve_bearer(Core(), "good", issuer="https://x.example"), "r12-good")
        self.assertEqual(seen["resource"], "https://x.example/mcp")
        self.assertIsNone(om.resolve_bearer(Core(), "bad", issuer="https://x.example"))


class MountedOnProductHandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pending = build_runtime(":memory:", allowed_origins=frozenset({"pending"}))
        server = serve("127.0.0.1", 0, runtime=pending)
        host, port = server.server_address[:2]
        cls.base = f"http://{host}:{port}"
        server.RequestHandlerClass.runtime = build_runtime(
            ":memory:", allowed_origins=frozenset({cls.base}))
        cls.server = server
        cls.thread = threading.Thread(target=server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_unauthenticated_mcp_challenge_carries_resource_metadata(self):
        req = Request(self.base + "/mcp", method="POST", data=b'{"jsonrpc":"2.0","id":1,"method":"ping"}',
                      headers={"Content-Type": "application/json"})
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 401)
        challenge = ctx.exception.headers.get("WWW-Authenticate", "")
        self.assertIn(f'resource_metadata="{self.base}/.well-known/oauth-protected-resource"', challenge)

    def test_wellknown_and_oauth_paths_are_routed_and_404_without_core(self):
        for path in (om.PROTECTED_RESOURCE_PATH, om.AUTH_SERVER_PATH, "/oauth/authorize"):
            with self.assertRaises(HTTPError) as ctx:
                urlopen(Request(self.base + path), timeout=10)
            self.assertEqual(ctx.exception.code, 404, path)
            self.assertEqual(json.loads(ctx.exception.read())["error"], "not_found")
        with self.assertRaises(HTTPError) as ctx:
            urlopen(Request(self.base + "/oauth/token", method="POST", data=b"grant_type=x",
                            headers={"Content-Type": "application/x-www-form-urlencoded"}), timeout=10)
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
