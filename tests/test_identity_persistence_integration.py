"""R12 contract checks against the current R11 persistence seam when present."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.identity import (
    AuthorizationError,
    ConsentChoices,
    IdentityService,
    ManualUIAdapter,
    R11IdentityBackend,
)

try:
    from src.persistence import LiveCorpusService
    from tests.support import repository
    from src.persistence.seed import minimal_thought
except ImportError:  # R11 is a parallel PR until its accepted merge lands.
    LiveCorpusService = None
    repository = None
    minimal_thought = None


LOCATION = {
    "kind": "synthetic_coarse",
    "region": "US-CA",
    "city": "San Diego",
    "lat": 32.71573642,
    "lon": -117.16108791,
    "precision": "city",
}
PRESENTATION = {"domain": "test", "topic": "identity", "cluster_id": "r12"}


@unittest.skipUnless(
    LiveCorpusService is not None,
    "R11 persistence package is not present on this parallel branch",
)
class R11IdentityIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "identity"
        self.live = LiveCorpusService(repository(self.path))
        self.identity = IdentityService(R11IdentityBackend(self.live))

    def tearDown(self):
        self.live.repo.close()
        self.tmp.cleanup()

    def test_private_create_versioned_update_consent_restart_revoke_delete(self):
        alice = self.identity.register("alice")
        bob = self.identity.register("bob")
        ui = ManualUIAdapter(self.identity, request_origin="https://resonance.local")
        created = ui.create_thought_session(
            alice.access_token,
            alice.csrf_token,
            thought_dna=minimal_thought("thought-r12-created", "thermal"),
            location=LOCATION,
            presentation=PRESENTATION,
        )
        self.assertEqual(created.version, 1)
        self.assertEqual((created.location["lat"], created.location["lon"]), (32.7, -117.2))
        self.assertFalse(created.is_discoverable())

        updated = ui.update_thought_session(
            alice.access_token,
            alice.csrf_token,
            created.session_id,
            thought_dna=minimal_thought("thought-r12-updated", "thermal"),
        )
        self.assertEqual(updated.version, 2)
        choices = ConsentChoices(
            share_thought_dna=True,
            share_display_profile=True,
            share_coarse_location=True,
            allow_intro_requests=True,
        )
        ui.set_consent(
            alice.access_token,
            alice.csrf_token,
            created.session_id,
            choices,
            confirmed=True,
        )
        with self.assertRaises(AuthorizationError):
            self.identity.consent_for(bob.access_token, created.session_id)

        self.live.repo.close()
        self.live = LiveCorpusService(repository(self.path))
        self.identity = IdentityService(R11IdentityBackend(self.live))
        ui = ManualUIAdapter(self.identity, request_origin="https://resonance.local")
        self.assertEqual(
            self.identity.authenticate(alice.access_token).actor_type,
            "human",
        )
        self.assertTrue(
            self.identity.consent_for(
                alice.access_token,
                created.session_id,
            ).allow_intro_requests
        )

        revoked = ui.revoke(
            alice.access_token,
            alice.csrf_token,
            created.session_id,
            confirmed=True,
        )
        self.assertFalse(revoked.is_discoverable())
        deleted = ui.delete(
            alice.access_token,
            alice.csrf_token,
            created.session_id,
            confirmed=True,
        )
        self.assertIsNotNone(deleted.deleted_at)

    def test_intro_opt_out_survives_failed_corpus_write_and_restart(self):
        alice = self.identity.register("alice")
        created = self.identity.create_thought_session(
            alice.access_token,
            thought_dna=minimal_thought("thought-r12-intro", "thermal"),
            location=LOCATION,
            presentation=PRESENTATION,
        )
        self.identity.set_consent(
            alice.access_token,
            created.session_id,
            ConsentChoices(share_thought_dna=True, allow_intro_requests=True),
            confirmed=True,
        )
        original = self.live.update_consent

        def fail_update(*args, **kwargs):
            raise RuntimeError("simulated corpus write failure")

        self.live.update_consent = fail_update
        with self.assertRaisesRegex(RuntimeError, "corpus write failure"):
            self.identity.set_consent(
                alice.access_token,
                created.session_id,
                ConsentChoices(share_thought_dna=False, allow_intro_requests=False),
                confirmed=True,
            )
        self.live.update_consent = original

        self.live.repo.close()
        self.live = LiveCorpusService(repository(self.path))
        restarted = IdentityService(R11IdentityBackend(self.live))
        self.assertFalse(
            restarted.consent_for(
                alice.access_token,
                created.session_id,
            ).allow_intro_requests
        )


if __name__ == "__main__":
    unittest.main()
