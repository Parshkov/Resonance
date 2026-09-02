"""R10 browser WebMCP registration, consent, retry, privacy, and source-fidelity tests."""

from __future__ import annotations

import copy
import json
import sys
import threading
import unittest
from http.error import HTTPError
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from demo.ui.server import load_replay  # noqa: E402
from demo.ui.webmcp_server import (  # noqa: E402
    STATE,
    WEBMCP_CONTRACT,
    WebMCPHandler,
)

EXPECTED_TOOLS = {
    "resonance_prepare_thought",
    "resonance_get_share_preview",
    "resonance_share_prepared_thought",
    "resonance_discover",
    "resonance_get_match",
    "resonance_update_consent",
}


class WebMCPSourceTests(unittest.TestCase):
    def test_browser_registers_real_document_model_context_tools(self):
        source = (REPO / "demo/ui/webmcp.mjs").read_text(encoding="utf-8")
        self.assertIn("document.modelContext", source)
        self.assertIn(
            "await modelContext.registerTool(tool, {signal: registrationController.signal})",
            source,
        )
        for name in EXPECTED_TOOLS:
            self.assertIn(f'"{name}"', source)
        self.assertIn("readOnlyHint: true", source)
        self.assertIn("untrustedContentHint: true", source)
        self.assertIn("options?.signal", source)
        self.assertIn('required: ["request_id", "confirm", "confirmation_token"]', source)
        self.assertIn('required: ["request_id", "shared"]', source)
        self.assertIn('required: ["result_id", "session_id"]', source)

    def test_webmcp_client_reconciles_cancelled_writes_from_authoritative_state(self):
        source = (REPO / "demo/ui/webmcp.mjs").read_text(encoding="utf-8")
        self.assertIn('error?.name !== "AbortError"', source)
        self.assertIn("reconcileCommitted(operation, requestId)", source)
        self.assertIn('jsonFetch("/api/webmcp/state")', source)
        self.assertIn("applyAuthoritativeState(state)", source)
        self.assertIn("/api/webmcp/operation?", source)

    def test_match_handler_does_not_reload_replay_fixture(self):
        source = (REPO / "demo/ui/webmcp_server.py").read_text(encoding="utf-8")
        match_handler = source.split("def _handle_match", 1)[1].split("def do_POST", 1)[0]
        self.assertNotIn("load_replay", match_handler)
        self.assertIn("STATE.discovery_record(result_id)", match_handler)

    def test_webmcp_client_contains_no_matching_or_reranking_logic(self):
        source = (REPO / "demo/ui/webmcp.mjs").read_text(encoding="utf-8")
        self.assertNotIn(".sort(", source)
        self.assertNotIn("Math.random", source)
        for internal in (
            "src.alignment", "src.engine", "src.fingerprint", "src.index",
            "src.retrieval", "src.scoring", "src.verifier",
        ):
            self.assertNotIn(internal, source)


class WebMCPHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class QuietHandler(WebMCPHandler):
            def log_message(self, format, *args):  # noqa: A002
                pass

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.server.server_address
        cls.base = f"http://{host}:{port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        STATE.reset()

    def get_json(self, path):
        with urlopen(self.base + path, timeout=15) as response:
            return response.status, response.headers, json.loads(response.read())

    def post_json(self, path, payload, *, origin=True, extra_headers=None):
        headers = {"Content-Type": "application/json"}
        if origin is True:
            headers["Origin"] = self.base
        elif isinstance(origin, str):
            headers["Origin"] = origin
        if extra_headers:
            headers.update(extra_headers)
        request = Request(
            self.base + path,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=15) as response:
            return response.status, response.headers, json.loads(response.read())

    def prepare_preview(self, note="judge flow", *, prefix="flow"):
        self.post_json(
            "/api/webmcp/consent",
            {"request_id": f"{prefix}-revoke", "shared": False},
        )
        _, _, prepared = self.post_json(
            "/api/webmcp/prepare",
            {"request_id": f"{prefix}-prepare", "note": note},
        )
        _, _, preview = self.get_json("/api/webmcp/preview")
        return prepared, preview

    def share_from_preview(self, preview, *, request_id):
        return self.post_json("/api/webmcp/share", {
            "request_id": request_id,
            "confirm": True,
            "confirmation_token": preview["confirmation_token"],
        })

    def test_root_injects_webmcp_and_security_headers(self):
        with urlopen(self.base + "/", timeout=15) as response:
            body = response.read().decode()
            self.assertIn('/webmcp.mjs', body)
            self.assertEqual(response.headers["Permissions-Policy"], "tools=(self)")
            self.assertEqual(response.headers["Cross-Origin-Opener-Policy"], "same-origin")
            self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])

    def test_prepare_is_private_preview_is_read_only_and_share_requires_preview_token(self):
        prepared, preview = self.prepare_preview()
        self.assertEqual(prepared["contract_version"], WEBMCP_CONTRACT)
        self.assertFalse(prepared["discoverable"])
        self.assertTrue(preview["requires_explicit_confirmation"])
        self.assertIn("thought", preview["will_become_discoverable"])
        self.assertTrue(preview["confirmation_token"])

        with self.assertRaises(HTTPError) as rejected:
            self.post_json("/api/webmcp/share", {
                "request_id": "share-false",
                "confirm": False,
                "confirmation_token": preview["confirmation_token"],
            })
        self.assertEqual(rejected.exception.code, 428)

        with self.assertRaises(HTTPError) as missing_token:
            self.post_json("/api/webmcp/share", {
                "request_id": "share-missing-token",
                "confirm": True,
            })
        self.assertEqual(missing_token.exception.code, 428)

        with self.assertRaises(HTTPError) as stale_token:
            self.post_json("/api/webmcp/share", {
                "request_id": "share-bad-token",
                "confirm": True,
                "confirmation_token": "not-the-preview-token",
            })
        self.assertEqual(stale_token.exception.code, 412)

        _, _, shared = self.share_from_preview(preview, request_id="share-good")
        self.assertTrue(shared["shared"])
        self.assertTrue(shared["discoverable"])
        _, _, state = self.get_json("/api/webmcp/state")
        self.assertFalse(state["draft_ready"])

    def test_duplicate_share_write_returns_existing_result_without_reapplying(self):
        _, preview = self.prepare_preview(prefix="duplicate")
        payload = {
            "request_id": "duplicate-share-1",
            "confirm": True,
            "confirmation_token": preview["confirmation_token"],
        }
        _, _, first = self.post_json("/api/webmcp/share", payload)
        _, _, second = self.post_json("/api/webmcp/share", payload)
        self.assertEqual(second, first)
        self.assertTrue(second["shared"])
        _, _, state = self.get_json("/api/webmcp/state")
        self.assertTrue(state["shared"])
        self.assertFalse(state["draft_ready"])

        _, _, operation = self.get_json(
            "/api/webmcp/operation?operation=share&request_id=duplicate-share-1"
        )
        self.assertTrue(operation["committed"])
        self.assertEqual(operation["result"], first)

    def test_idempotency_key_cannot_be_reused_with_different_payload(self):
        _, _, first = self.post_json(
            "/api/webmcp/prepare",
            {"request_id": "prepare-key", "note": "one"},
        )
        self.assertFalse(first["discoverable"])
        with self.assertRaises(HTTPError) as conflict:
            self.post_json(
                "/api/webmcp/prepare",
                {"request_id": "prepare-key", "note": "two"},
            )
        self.assertEqual(conflict.exception.code, 409)

    def test_cancel_reconcile_path_finds_committed_write_and_retry_is_noop(self):
        payload = {"request_id": "cancelled-revoke-1", "shared": False}
        self.post_json("/api/webmcp/consent", payload)
        _, _, committed = self.get_json(
            "/api/webmcp/operation?operation=consent&request_id=cancelled-revoke-1"
        )
        self.assertTrue(committed["committed"])
        self.assertTrue(committed["result"]["revoked"])
        _, _, replay = self.post_json("/api/webmcp/consent", payload)
        self.assertEqual(replay, committed["result"])
        _, _, state = self.get_json("/api/webmcp/state")
        self.assertFalse(state["shared"])

    def test_uncommitted_operation_status_is_explicitly_retryable(self):
        with self.assertRaises(HTTPError) as missing:
            self.get_json(
                "/api/webmcp/operation?operation=share&request_id=not-committed"
            )
        self.assertEqual(missing.exception.code, 404)
        payload = json.loads(missing.exception.read())
        self.assertEqual(payload["error"], "operation_not_committed")
        self.assertTrue(payload["retryable"])

    def test_revoke_blocks_discovery_and_direct_reenable_is_forbidden(self):
        _, _, revoked = self.post_json(
            "/api/webmcp/consent",
            {"request_id": "revoke-1", "shared": False},
        )
        self.assertTrue(revoked["revoked"])
        with self.assertRaises(HTTPError) as blocked:
            self.get_json("/api/webmcp/discover?source=replay")
        self.assertEqual(blocked.exception.code, 403)

        with self.assertRaises(HTTPError) as bypass:
            self.post_json(
                "/api/webmcp/consent",
                {"request_id": "reenable-shortcut", "shared": True},
            )
        self.assertEqual(bypass.exception.code, 409)

        _, _, prepared = self.post_json(
            "/api/webmcp/prepare",
            {"request_id": "restore-prepare", "note": "restore"},
        )
        self.assertFalse(prepared["discoverable"])
        _, _, preview = self.get_json("/api/webmcp/preview")
        self.share_from_preview(preview, request_id="restore-share")
        _, _, discovery = self.get_json("/api/webmcp/discover?source=replay")
        self.assertEqual(discovery["contract_version"], WEBMCP_CONTRACT)
        self.assertRegex(discovery["result_id"], r"^result-[0-9a-f]{24}$")
        rows = discovery["matches_in_backend_order"]
        self.assertGreaterEqual(len(rows), 4)
        self.assertTrue(all(row["display"]["share_state"] == "discoverable" for row in rows))

    def test_live_discovery_match_evidence_is_bound_to_same_exact_result(self):
        live_payload = copy.deepcopy(load_replay())
        live_row = next(
            row for row in live_payload["matches"]
            if row.get("display", {}).get("share_state") == "discoverable"
        )
        live_row["display"]["topic"] = "LIVE SOURCE SENTINEL — not replay"

        with patch("demo.ui.webmcp_server._discovery_payload", return_value=live_payload):
            _, _, discovery = self.get_json("/api/webmcp/discover?source=live")

        self.assertEqual(discovery["source"], "live")
        result_id = discovery["result_id"]
        session_id = live_row["session_id"]
        _, _, match = self.get_json(
            f"/api/webmcp/match?result_id={result_id}&session_id={session_id}"
        )
        self.assertEqual(match["source"], "live")
        self.assertEqual(match["result_id"], result_id)
        self.assertEqual(match["match"]["display"]["topic"], "LIVE SOURCE SENTINEL — not replay")

    def test_match_requires_a_discovery_result_and_never_falls_back_to_replay(self):
        with self.assertRaises(HTTPError) as missing:
            self.get_json("/api/webmcp/match?session_id=ses-gabe-warehouse")
        self.assertEqual(missing.exception.code, 400)

        with self.assertRaises(HTTPError) as unknown:
            self.get_json(
                "/api/webmcp/match?result_id=result-000000000000000000000000&session_id=ses-gabe-warehouse"
            )
        self.assertEqual(unknown.exception.code, 404)
        payload = json.loads(unknown.exception.read())
        self.assertEqual(payload["error"], "discovery_result_not_found")

    def test_revocation_invalidates_discovery_result_ids(self):
        _, _, discovery = self.get_json("/api/webmcp/discover?source=replay")
        result_id = discovery["result_id"]
        session_id = discovery["matches_in_backend_order"][0]["session_id"]
        self.post_json(
            "/api/webmcp/consent",
            {"request_id": "invalidate-result-revoke", "shared": False},
        )
        _, preview = self.prepare_preview("restore after invalidation", prefix="invalidate")
        self.share_from_preview(preview, request_id="invalidate-share")
        with self.assertRaises(HTTPError) as expired:
            self.get_json(
                f"/api/webmcp/match?result_id={result_id}&session_id={session_id}"
            )
        self.assertEqual(expired.exception.code, 404)

    def test_revocation_invalidates_an_existing_preview_token(self):
        _, preview = self.prepare_preview("stale-after-revoke", prefix="stale")
        self.post_json(
            "/api/webmcp/consent",
            {"request_id": "stale-revoke-2", "shared": False},
        )
        with self.assertRaises(HTTPError) as stale:
            self.post_json("/api/webmcp/share", {
                "request_id": "stale-share",
                "confirm": True,
                "confirmation_token": preview["confirmation_token"],
            })
        self.assertEqual(stale.exception.code, 412)

    def test_match_projection_has_evidence_but_no_contact_fields(self):
        _, _, discovery = self.get_json("/api/webmcp/discover?source=replay")
        result_id = discovery["result_id"]
        session_id = discovery["matches_in_backend_order"][0]["session_id"]
        _, _, result = self.get_json(
            f"/api/webmcp/match?result_id={result_id}&session_id={session_id}"
        )
        serialized = json.dumps(result).lower()
        self.assertIn("evidence", result["match"])
        self.assertEqual(result["source"], "replay")
        self.assertNotIn("email", serialized)
        self.assertNotIn("phone", serialized)
        self.assertNotIn("contact", serialized)

    def test_cross_origin_and_cross_site_writes_are_rejected(self):
        with self.assertRaises(HTTPError) as rejected:
            self.post_json(
                "/api/webmcp/consent",
                {"request_id": "evil-1", "shared": False},
                origin="https://attacker.example",
            )
        self.assertEqual(rejected.exception.code, 403)

        with self.assertRaises(HTTPError) as fetch_metadata_rejected:
            self.post_json(
                "/api/webmcp/consent",
                {"request_id": "evil-2", "shared": False},
                extra_headers={"Sec-Fetch-Site": "cross-site"},
            )
        self.assertEqual(fetch_metadata_rejected.exception.code, 403)

    def test_error_shape_distinguishes_validation_confirmation_and_retryability(self):
        with self.assertRaises(HTTPError) as validation:
            self.post_json(
                "/api/webmcp/prepare",
                {"request_id": "bad id with spaces", "note": "x"},
            )
        validation_payload = json.loads(validation.exception.read())
        self.assertEqual(validation_payload["error"], "validation_failed")
        self.assertFalse(validation_payload["retryable"])

        self.post_json(
            "/api/webmcp/consent",
            {"request_id": "private-first", "shared": False},
        )
        with self.assertRaises(HTTPError) as confirmation:
            self.post_json(
                "/api/webmcp/consent",
                {"request_id": "direct-enable", "shared": True},
            )
        confirmation_payload = json.loads(confirmation.exception.read())
        self.assertEqual(confirmation_payload["error"], "confirmation_required")
        self.assertFalse(confirmation_payload["retryable"])


if __name__ == "__main__":
    unittest.main()
