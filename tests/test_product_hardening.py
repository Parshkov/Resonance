"""Product hardening (2026-09-04): registration limit, issuer allowlist,
audience-bound bearer, demo-persona labelling, label scrubbing."""

import json
import sys
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.product import server as product_server  # noqa: E402
from src.product.mcp_bridge import build_thought_dna  # noqa: E402
from src.product.server import build_runtime, serve  # noqa: E402
from src.remote.oauth import GrantStore, OAuthCore, OAuthError  # noqa: E402


class RegistrationLimitTests(unittest.TestCase):
    def test_forwarded_address_is_limited_but_loopback_is_not(self):
        product_server._registration_hits.clear()
        for _ in range(product_server.REGISTRATION_LIMIT):
            self.assertTrue(product_server.registration_allowed("203.0.113.9", now=100.0))
        self.assertFalse(product_server.registration_allowed("203.0.113.9", now=101.0))
        # the window slides
        self.assertTrue(product_server.registration_allowed(
            "203.0.113.9", now=101.0 + product_server.REGISTRATION_WINDOW_SECONDS + 1))
        for _ in range(product_server.REGISTRATION_LIMIT + 5):
            self.assertTrue(product_server.registration_allowed("127.0.0.1"))

    def test_http_guest_creation_returns_429_over_the_limit(self):
        runtime = build_runtime(":memory:", allowed_origins=frozenset({"http://127.0.0.1"}), seed=False)
        httpd = serve("127.0.0.1", 0, runtime=runtime)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        product_server._registration_hits.clear()
        try:
            headers = {"Content-Type": "application/json", "X-Forwarded-For": "198.51.100.7"}
            statuses = []
            for _ in range(product_server.REGISTRATION_LIMIT + 1):
                try:
                    with urlopen(Request(base + "/api/product/guest", data=b"{}", method="POST", headers=headers)) as r:
                        statuses.append(r.status)
                except HTTPError as exc:
                    statuses.append(exc.code)
                    self.assertEqual(json.loads(exc.read())["error"], "rate_limited")
            self.assertEqual(statuses[-1], 429)
            self.assertTrue(all(s == 200 for s in statuses[:-1]))
        finally:
            httpd.shutdown()
            httpd.server_close()
            product_server._registration_hits.clear()


class AudienceBindingTests(unittest.TestCase):
    def test_access_token_bound_to_another_resource_is_refused(self):
        runtime = build_runtime(":memory:", allowed_origins=frozenset({"http://127.0.0.1"}), seed=False)
        store = GrantStore()
        core = OAuthCore(runtime.identity, store)
        creds = runtime.identity.register_guest()
        token = creds.access_token
        # no audience record (debug-minted key): structural acceptance
        self.assertEqual(core.resolve_bearer(token, resource="http://127.0.0.1/mcp"), token)
        store.put_access(token, {"user_id": creds.user_id, "resource": "https://other.example/mcp",
                                 "client_id": "c", "expires": 9e12})
        self.assertIsNone(core.resolve_bearer(token, resource="http://127.0.0.1/mcp"))
        self.assertEqual(core.resolve_bearer(token, resource="https://other.example/mcp"), token)

    def test_token_response_fails_closed_when_audience_record_cannot_persist(self):
        class BrokenAudienceStore(GrantStore):
            def put_access(self, token, record):
                raise RuntimeError("storage unavailable")

        runtime = build_runtime(
            ":memory:", allowed_origins=frozenset({"http://127.0.0.1"}), seed=False
        )
        core = OAuthCore(runtime.identity, BrokenAudienceStore())
        creds = runtime.identity.register_guest(actor_type="agent")

        with self.assertRaisesRegex(OAuthError, "could not bind access token"):
            core._token_response(
                creds.access_token,
                "resonance",
                "http://127.0.0.1/mcp",
                "client-test",
            )
        with self.assertRaises(Exception):
            runtime.identity.authenticate(creds.access_token)


class DemoPersonaAndScrubTests(unittest.TestCase):
    def test_seeded_rows_are_flagged_and_labels_are_scrubbed(self):
        runtime = build_runtime(":memory:", allowed_origins=frozenset({"http://127.0.0.1"}), seed=True)
        product = runtime.product
        creds = product.register_guest()
        thought = {"nodes": [{"label": "sustained fast-charging load from bob@acme.com", "role": "problem"},
                             {"label": "heat accumulation inside the cell", "role": "state"},
                             {"label": "electrolyte degradation", "role": "mechanism"},
                             {"label": "cell failure", "role": "outcome"},
                             {"label": "active cooling", "role": "method"}],
                   "relations": [{"source": "n0", "target": "n1", "type": "causes"},
                                 {"source": "n1", "target": "n2", "type": "causes"},
                                 {"source": "n2", "target": "n3", "type": "causes"},
                                 {"source": "n4", "target": "n1", "type": "prevents"}]}
        dna = build_thought_dna(thought, human_id=creds.user_id)
        self.assertNotIn("acme", json.dumps(dna))
        prepared = product.prepare_structured(creds.access_token, dna,
                                              presentation={"domain": "engineering", "topic": "thermal", "cluster_id": "c1"},
                                              coarse_location=None, intent=None)
        preview = product.preview(creds.access_token, prepared["draft_id"])
        shared = product.share_prepared(creds.access_token, prepared["draft_id"],
                                        confirmation_token=preview["confirmation_token"], confirmed=True)
        session_id = shared["session_id"]
        result = product.discover(creds.access_token, session_id, k=8)
        self.assertTrue(result["matches"])
        self.assertTrue(all(m["display"]["demo_persona"] is True for m in result["matches"]))


if __name__ == "__main__":
    unittest.main()


class DemoSeedPolicyTests(unittest.TestCase):
    def test_persistent_database_is_not_seeded_by_default_and_purge_demo_cleans_a_seeded_one(self):
        import tempfile
        from pathlib import Path
        from src.persistence.seed import purge_demo
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "live.sqlite3")
            rt = build_runtime(db, allowed_origins=frozenset({"http://127.0.0.1"}), confirmation_secret=b"x" * 32)
            self.assertEqual(rt.live.health().sessions, 0)
            rt.live.repo.close()
            rt = build_runtime(db, allowed_origins=frozenset({"http://127.0.0.1"}), confirmation_secret=b"x" * 32, seed=True)
            self.assertEqual(rt.live.health().sessions, 25)
            creds = rt.product.register_guest()
            self.assertIsNotNone(rt.live.get_user(creds.user_id))
            result = purge_demo(rt.live)
            self.assertEqual(result["sessions_deleted"], 25)
            self.assertGreater(result["users_revoked"], 0)
            self.assertEqual(rt.live.health().discoverable, 0)
            self.assertIsNotNone(rt.live.get_user(creds.user_id))      # real account untouched
            self.assertFalse(rt.live.get_user(creds.user_id).hidden)
            self.assertEqual(purge_demo(rt.live), {"sessions_deleted": 0, "users_revoked": 0})
            rt.live.repo.close()

    def test_in_memory_runtime_is_seeded_for_local_development(self):
        rt = build_runtime(":memory:", allowed_origins=frozenset({"http://127.0.0.1"}))
        self.assertEqual(rt.live.health().sessions, 25)


class ReadinessTests(unittest.TestCase):
    def test_health_reports_engine_identity_and_demo_presence(self):
        from src.engine import ENGINE_VERSION
        runtime = build_runtime(":memory:", allowed_origins=frozenset({"http://127.0.0.1"}))
        httpd = serve("127.0.0.1", 0, runtime=runtime)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with urlopen(f"http://127.0.0.1:{httpd.server_address[1]}/api/product/health") as r:
                health = json.loads(r.read())
        finally:
            httpd.shutdown()
            httpd.server_close()
        self.assertEqual(health["engine"]["engine_version"], ENGINE_VERSION)
        self.assertEqual(health["engine"]["verifier_config_hash"], runtime.live.engine.verifier.config_hash)
        self.assertTrue(health["corpus"]["demo_personas_present"])
        self.assertEqual(health["corpus"]["demo_sessions"], 25)
        self.assertEqual(health["corpus"]["volunteer_sessions"], 0)

    def test_startup_purge_is_gated_by_the_environment_variable(self):
        runtime = build_runtime(":memory:", allowed_origins=frozenset({"http://127.0.0.1"}))
        self.assertIsNone(product_server.startup_purge_demo(runtime, {}))
        self.assertEqual(product_server.corpus_summary(runtime)["demo_sessions"], 25)
        result = product_server.startup_purge_demo(runtime, {"RESONANCE_PURGE_DEMO": "1"})
        self.assertEqual(result["sessions_deleted"], 25)
        self.assertFalse(product_server.corpus_summary(runtime)["demo_personas_present"])
        self.assertEqual(product_server.startup_purge_demo(runtime, {"RESONANCE_PURGE_DEMO": "1"}),
                         {"sessions_deleted": 0, "users_revoked": 0})
