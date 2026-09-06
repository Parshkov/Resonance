"""R12C durable R11/R12/R12B integration and transport-parity tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.identity import CsrfError, IdentityService, R11IdentityBackend
from src.ingestion import (
    ConfirmationError,
    DraftNotFound,
    IdentityIngestionService,
    IngestionError,
    IngestionService,
    ManualIngestionAdapter,
    RemoteMCPIngestionAdapter,
    ShareIntent,
    WebMCPIngestionAdapter,
)
from src.persistence import LiveCorpusService, PersistenceConflictError
from tests.support import repository
from src.persistence.seed import minimal_thought


ORIGIN = "https://app.resonance.example"
LOCATION = {
    "kind": "synthetic_coarse",
    "region": "US-CA",
    "city": "San Diego",
    "lat": 32.7,
    "lon": -117.2,
    "precision": "city",
}


class DurableIngestionIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "ingestion"
        self.live = LiveCorpusService(repository(self.path))
        self.identity = IdentityService(
            R11IdentityBackend(self.live),
            allowed_origins=frozenset({ORIGIN}),
        )
        self.alice = self.identity.register("alice")
        self.bob = self.identity.register("bob")
        self.ingestion = IdentityIngestionService(
            self.identity,
            core=IngestionService(secret=b"r12c-integration-secret"),
        )
        self.manual = ManualIngestionAdapter(self.ingestion, request_origin=ORIGIN)

    def tearDown(self) -> None:
        self.live.repo.close()
        self.tmp.cleanup()

    def _prepare(self, thought_id: str = "thought-r12c") -> dict:
        return self.manual.prepare_structured(
            self.alice.access_token,
            minimal_thought(thought_id, "thermal"),
            csrf_token=self.alice.csrf_token,
            presentation={
                "topic": "thermal",
                "domain": "engineering",
                "cluster_id": "r12c-test",
            },
            coarse_location=LOCATION,
            intent=ShareIntent(
                share_display_profile=True,
                share_coarse_location=True,
                receive_intro_requests=True,
            ),
        )

    def _restart(self) -> None:
        self.live.repo.close()
        self.live = LiveCorpusService(repository(self.path))
        self.identity = IdentityService(
            R11IdentityBackend(self.live),
            allowed_origins=frozenset({ORIGIN}),
        )
        self.ingestion = IdentityIngestionService(
            self.identity,
            core=IngestionService(secret=b"r12c-integration-secret"),
        )
        self.manual = ManualIngestionAdapter(self.ingestion, request_origin=ORIGIN)

    def test_durable_service_requires_stable_confirmation_secret(self) -> None:
        with self.assertRaisesRegex(ValueError, "stable confirmation_secret"):
            IdentityIngestionService(self.identity)

    def test_prepare_is_durable_private_then_restart_preview_and_share(self) -> None:
        prepared = self._prepare()
        session = self.live.get_session(prepared["session_id"])
        self.assertTrue(prepared["durable"])
        self.assertFalse(session.is_discoverable())
        self.assertEqual(session.thought_dna["source"]["text"], "")
        before = self.manual.preview(self.alice.access_token, prepared["draft_id"])

        self._restart()
        after = self.manual.preview(self.alice.access_token, prepared["draft_id"])
        self.assertEqual(after["confirmation_token"], before["confirmation_token"])
        receipt = self.manual.share_prepared(
            self.alice.access_token,
            prepared["draft_id"],
            confirmation_token=after["confirmation_token"],
            confirmed=True,
            csrf_token=self.alice.csrf_token,
        )
        self.assertTrue(receipt["discoverable"])
        self.assertTrue(self.live.get_session(prepared["session_id"]).is_discoverable())
        with self.assertRaises(DraftNotFound):
            self.manual.preview(self.alice.access_token, prepared["draft_id"])

    def test_other_user_cannot_preview_share_or_discard_draft(self) -> None:
        prepared = self._prepare("thought-owner-scope")
        for operation in ("preview", "share", "discard"):
            with self.assertRaises(DraftNotFound, msg=operation):
                if operation == "preview":
                    self.ingestion.preview(self.bob.access_token, prepared["draft_id"])
                elif operation == "share":
                    self.ingestion.share_prepared(
                        self.bob.access_token,
                        prepared["draft_id"],
                        confirmation_token="attacker-token",
                        confirmed=True,
                    )
                else:
                    self.ingestion.discard(
                        self.bob.access_token,
                        prepared["draft_id"],
                        confirmed=True,
                    )
        self.assertFalse(self.live.get_session(prepared["session_id"]).is_discoverable())

    def test_manual_prepare_web_preview_remote_share_use_one_exact_artifact(self) -> None:
        prepared = self._prepare("thought-transport-parity")
        web = WebMCPIngestionAdapter(self.ingestion, request_origin=ORIGIN)
        remote = RemoteMCPIngestionAdapter(self.ingestion)
        preview = web.resonance_get_share_preview(
            self.alice.access_token,
            prepared["draft_id"],
        )
        expected = dict(preview["thought_dna"])
        self.assertEqual(preview["_meta"], {"untrustedContentHint": True})
        receipt = remote.resonance_share_prepared_thought(
            self.alice.access_token,
            prepared["draft_id"],
            confirmation_token=preview["confirmation_token"],
            confirmed=True,
        )
        stored = self.live.get_session(receipt["session_id"])
        self.assertEqual(dict(stored.thought_dna), expected)
        self.assertTrue(stored.is_discoverable())
        self.assertTrue(web.untrusted_content_hint)
        self.assertTrue(remote.untrusted_content_hint)

    def test_canonical_tool_prepare_action_requires_exactly_one_input(self) -> None:
        web = WebMCPIngestionAdapter(self.ingestion, request_origin=ORIGIN)
        with self.assertRaises(IngestionError):
            web.resonance_prepare_thought(
                self.alice.access_token,
                csrf_token=self.alice.csrf_token,
            )
        with self.assertRaises(IngestionError):
            web.resonance_prepare_thought(
                self.alice.access_token,
                candidate=minimal_thought("thought-both", "security"),
                context="A causes B",
                csrf_token=self.alice.csrf_token,
            )
        prepared = web.resonance_prepare_thought(
            self.alice.access_token,
            candidate=minimal_thought("thought-tool", "security"),
            csrf_token=self.alice.csrf_token,
            presentation={
                "topic": "tools",
                "domain": "test",
                "cluster_id": "r12c-test",
            },
        )
        self.assertEqual(prepared["_meta"], {"untrustedContentHint": True})

    def test_discard_tombstones_private_draft_and_raw_source_never_persists(self) -> None:
        private_source = "Project Juniper has an unreleased cobalt budget discussion"
        prepared = self.manual.prepare_raw_text(
            self.alice.access_token,
            private_source,
            csrf_token=self.alice.csrf_token,
        )
        result = self.manual.discard(
            self.alice.access_token,
            prepared["draft_id"],
            confirmed=True,
            csrf_token=self.alice.csrf_token,
        )
        self.assertTrue(result["discarded"])
        stored = self.live.get_session(prepared["session_id"])
        self.assertIsNotNone(stored.deleted_at)
        serialized = json.dumps(self.live.export_backup())
        self.assertNotIn(private_source, serialized)

        self._restart()
        with self.assertRaises(DraftNotFound):
            self.manual.preview(self.alice.access_token, prepared["draft_id"])

    def test_confirmation_and_same_origin_are_required_without_orphan_draft(self) -> None:
        evil = ManualIngestionAdapter(
            self.ingestion,
            request_origin="https://evil.example",
        )
        with self.assertRaises(CsrfError):
            evil.prepare_structured(
                self.alice.access_token,
                minimal_thought("thought-evil-origin", "security"),
                csrf_token=self.alice.csrf_token,
            )
        self.assertEqual(len(self.live.repo.list_sessions(include_deleted=True)), 0)

        prepared = self._prepare("thought-confirmation")
        preview = self.manual.preview(self.alice.access_token, prepared["draft_id"])
        with self.assertRaises(ConfirmationError):
            self.manual.share_prepared(
                self.alice.access_token,
                prepared["draft_id"],
                confirmation_token=preview["confirmation_token"],
                confirmed=False,
                csrf_token=self.alice.csrf_token,
            )
        self.assertFalse(self.live.get_session(prepared["session_id"]).is_discoverable())

    def test_ambiguous_share_commit_retries_without_duplicate_session(self) -> None:
        prepared = self._prepare("thought-ambiguous-share")
        preview = self.manual.preview(self.alice.access_token, prepared["draft_id"])
        original = self.live.update_consent
        injected = {"done": False}

        def commit_then_fail(*args, **kwargs):
            result = original(*args, **kwargs)
            if not injected["done"]:
                injected["done"] = True
                raise RuntimeError("response lost after durable commit")
            return result

        self.live.update_consent = commit_then_fail
        with self.assertRaisesRegex(RuntimeError, "response lost"):
            self.manual.share_prepared(
                self.alice.access_token,
                prepared["draft_id"],
                confirmation_token=preview["confirmation_token"],
                confirmed=True,
                csrf_token=self.alice.csrf_token,
            )
        self.assertTrue(self.ingestion.core.has_draft(prepared["draft_id"]))
        self.live.update_consent = original
        receipt = self.manual.share_prepared(
            self.alice.access_token,
            prepared["draft_id"],
            confirmation_token=preview["confirmation_token"],
            confirmed=True,
            csrf_token=self.alice.csrf_token,
        )
        self.assertTrue(receipt["shared"])
        sessions = self.live.repo.list_sessions(include_deleted=True)
        self.assertEqual([item.session_id for item in sessions], [prepared["session_id"]])

    def test_unrelated_private_row_change_invalidates_prepared_share_version(self) -> None:
        prepared = self._prepare("thought-stale-preview")
        preview = self.manual.preview(self.alice.access_token, prepared["draft_id"])
        self.identity.update_metadata(
            self.alice.access_token,
            prepared["session_id"],
            presentation={
                "topic": "changed",
                "domain": "engineering",
                "cluster_id": "r12c-test",
            },
        )
        with self.assertRaises(PersistenceConflictError):
            self.manual.share_prepared(
                self.alice.access_token,
                prepared["draft_id"],
                confirmation_token=preview["confirmation_token"],
                confirmed=True,
                csrf_token=self.alice.csrf_token,
            )
        self.assertFalse(self.live.get_session(prepared["session_id"]).is_discoverable())

    def test_agent_cannot_supply_owner_or_consent_controls(self) -> None:
        candidate = minimal_thought("thought-spoof", "security")
        candidate["owner_id"] = self.bob.user_id
        candidate["consent"] = {"share_enabled": True}
        with self.assertRaises(IngestionError):
            self.manual.prepare_structured(
                self.alice.access_token,
                candidate,
                csrf_token=self.alice.csrf_token,
            )
        self.assertEqual(len(self.live.repo.list_sessions(include_deleted=True)), 0)


if __name__ == "__main__":
    unittest.main()
