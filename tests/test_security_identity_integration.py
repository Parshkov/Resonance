"""R12B enforcement tests over the current R11/R12 product path."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.identity import (
    AuthorizationError,
    ConsentChoices,
    CsrfError,
    IdentityService,
    ManualUIAdapter,
    R11IdentityBackend,
)
from src.identity.models import IdentityValidationError
from src.persistence import LiveCorpusService
from tests.support import repository
from src.persistence.seed import minimal_thought
from src.security import AuthorizationDenied, PayloadBounds, ResourceRef


ORIGIN = "https://app.resonance.example"
LOCATION = {
    "kind": "synthetic_coarse",
    "region": "US-CA",
    "city": "San Diego",
    "lat": 32.7,
    "lon": -117.2,
    "precision": "city",
}
PRESENTATION = {"domain": "test", "topic": "security", "cluster_id": "r12b"}


class DurableSecurityIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "security"
        self.live = LiveCorpusService(repository(self.path))
        self.identity = IdentityService(
            R11IdentityBackend(self.live),
            allowed_origins=frozenset({ORIGIN}),
        )
        self.alice = self.identity.register("alice")
        self.bob = self.identity.register("bob")
        self.ui = ManualUIAdapter(self.identity, request_origin=ORIGIN)

    def tearDown(self) -> None:
        self.live.repo.close()
        self.tmp.cleanup()

    def _create_alice(self, thought_id: str = "thought-r12b"):
        return self.ui.create_thought_session(
            self.alice.access_token,
            self.alice.csrf_token,
            thought_dna=minimal_thought(thought_id, "security"),
            location=LOCATION,
            presentation=PRESENTATION,
        )

    def _share(self, session_id: str) -> None:
        self.ui.set_consent(
            self.alice.access_token,
            self.alice.csrf_token,
            session_id,
            ConsentChoices(
                share_thought_dna=True,
                share_display_profile=True,
                share_coarse_location=True,
                allow_intro_requests=True,
            ),
            confirmed=True,
        )

    def _restart(self) -> None:
        self.live.repo.close()
        self.live = LiveCorpusService(repository(self.path))
        self.identity = IdentityService(
            R11IdentityBackend(self.live),
            allowed_origins=frozenset({ORIGIN}),
        )

    def test_product_mutations_consult_policy_and_persist_minimized_decisions(self) -> None:
        session = self._create_alice()
        with self.assertRaises(AuthorizationError):
            self.identity.set_consent(
                self.bob.access_token,
                session.session_id,
                ConsentChoices(share_thought_dna=True),
                confirmed=True,
            )
        events = [
            event for event in self.live.repo.list_audit()
            if event.event_type == "security.policy.decision"
        ]
        self.assertEqual(events[0].payload["action"], "session:create")
        self.assertEqual(events[-1].payload["decision"], "deny")
        serialized = json.dumps([event.to_public_dict() for event in events])
        for forbidden in (
            self.alice.access_token,
            self.alice.csrf_token,
            "thought-dna/0.1",
            "authorization",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_same_protocol_session_rechecks_revoke_and_rejects_other_subject(self) -> None:
        session = self._create_alice("thought-grant-drift")
        self._share(session.session_id)
        protocol_id = self.identity.bind_protocol_session(
            self.bob.access_token,
            client_id="remote-mcp",
            protocol_session_id="mcp-bob",
        )
        visible = self.identity.authorize_discovery(
            self.bob.access_token,
            session.session_id,
            client_id="remote-mcp",
            protocol_session_id=protocol_id,
        )
        self.assertEqual(visible["person"]["display_label"], "alice")
        with self.assertRaises(AuthorizationError):
            self.identity.authorize_discovery(
                self.alice.access_token,
                session.session_id,
                client_id="remote-mcp",
                protocol_session_id=protocol_id,
            )
        self.ui.revoke(
            self.alice.access_token,
            self.alice.csrf_token,
            session.session_id,
            confirmed=True,
        )
        with self.assertRaises(AuthorizationError):
            self.identity.authorize_discovery(
                self.bob.access_token,
                session.session_id,
                client_id="remote-mcp",
                protocol_session_id=protocol_id,
            )

    def test_block_is_durable_and_immediately_removes_discovery(self) -> None:
        session = self._create_alice("thought-block")
        self._share(session.session_id)
        self.identity.authorize_discovery(self.bob.access_token, session.session_id)
        self.identity.block_user(self.bob.access_token, self.alice.user_id, confirmed=True)
        with self.assertRaises(AuthorizationError):
            self.identity.authorize_discovery(self.bob.access_token, session.session_id)

        self._restart()
        with self.assertRaises(AuthorizationError):
            self.identity.authorize_discovery(self.bob.access_token, session.session_id)

    def test_revoked_auth_session_cannot_reuse_a_bound_protocol_session(self) -> None:
        session = self._create_alice("thought-auth-revoke")
        protocol_id = self.identity.bind_protocol_session(
            self.alice.access_token,
            client_id="remote-mcp",
            protocol_session_id="mcp-alice",
        )
        context = self.identity.request_context(
            self.alice.access_token,
            client_id="remote-mcp",
        )
        self.identity.logout(self.alice.access_token)
        with self.assertRaises(AuthorizationDenied):
            self.identity.security_policy.authorize(
                context,
                "session:read_private",
                ResourceRef("session", session.session_id),
                protocol_session_id=protocol_id,
            )

    def test_cookie_origin_and_payload_bounds_fail_before_storage(self) -> None:
        evil = ManualUIAdapter(self.identity, request_origin="https://evil.example")
        with self.assertRaises(CsrfError):
            evil.create_thought_session(
                self.alice.access_token,
                self.alice.csrf_token,
                thought_dna=minimal_thought("thought-evil", "security"),
                location=LOCATION,
                presentation=PRESENTATION,
            )
        self.identity.payload_bounds = PayloadBounds(max_nodes=1)
        oversized = minimal_thought("thought-large", "security")
        oversized["nodes"].append(dict(oversized["nodes"][0]) | {"node_id": "n-extra"})
        with self.assertRaises(IdentityValidationError):
            self.identity.create_thought_session(
                self.alice.access_token,
                thought_dna=oversized,
                location=LOCATION,
                presentation=PRESENTATION,
            )
        self.assertIsNone(self.live.repo.get_session_by_thought("thought-large"))

    def test_account_export_contains_owner_data_but_no_credentials(self) -> None:
        session = self._create_alice("thought-export")
        exported = self.identity.export_account(self.alice.access_token)
        self.assertEqual(exported["user"]["user_id"], self.alice.user_id)
        self.assertEqual(exported["sessions"][0]["session_id"], session.session_id)
        serialized = json.dumps(exported)
        self.assertNotIn(self.alice.access_token, serialized)
        self.assertNotIn(self.alice.csrf_token, serialized)
        self.assertNotIn(self.alice.recovery_secret, serialized)

    def test_account_revocation_anonymizes_profile_and_hides_sessions(self) -> None:
        session = self._create_alice("thought-delete-account")
        self._share(session.session_id)
        self.identity.revoke_account(self.alice.access_token, confirmed=True)
        user = self.live.get_user(self.alice.user_id)
        self.assertEqual(user.display_label, "Deleted user")
        self.assertEqual(user.avatar_placeholder, "deleted")
        self.assertIsNotNone(user.revoked_at)
        self.assertIsNone(self.live.public_session_view(session.session_id))

    def test_backup_restore_preserves_durable_block_policy(self) -> None:
        session = self._create_alice("thought-backup-policy")
        self._share(session.session_id)
        self.identity.block_user(self.bob.access_token, self.alice.user_id, confirmed=True)
        backup = self.live.export_backup()

        restored_path = Path(self.tmp.name) / "restored"
        restored_live = LiveCorpusService(repository(restored_path))
        try:
            restored_live.import_backup(backup)
            restored = IdentityService(
                R11IdentityBackend(restored_live),
                allowed_origins=frozenset({ORIGIN}),
            )
            with self.assertRaises(AuthorizationError):
                restored.authorize_discovery(self.bob.access_token, session.session_id)
        finally:
            restored_live.repo.close()


if __name__ == "__main__":
    unittest.main()
