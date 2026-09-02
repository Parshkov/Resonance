"""Focused crash/restart regressions for the reopened R11 mission."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from src.graph import ThoughtGraph
from src.persistence import LiveCorpusService, PersistenceStaleIndexError, SQLiteRepository
from src.persistence.models import ConsentState
from src.persistence.seed import minimal_thought


DISCOVERABLE = {
    "share_enabled": True,
    "share_thought_dna": True,
    "share_coarse_location": False,
    "share_display_profile": True,
}
LOCATION = {
    "kind": "synthetic_coarse",
    "region": "Test",
    "city": "Test",
    "lat": 10.0,
    "lon": 20.0,
    "precision": "city",
}
PRESENTATION = {"domain": "test", "topic": "restart", "cluster_id": "r11"}


def make_service(path: Path) -> tuple[LiveCorpusService, object]:
    service = LiveCorpusService(SQLiteRepository(path))
    service.create_user("person-restart", display_label="Restart")
    session = service.create_session(
        session_id="ses-restart",
        user_id="person-restart",
        thought_dna=minimal_thought("thought-restart", "thermal"),
        consent=DISCOVERABLE,
        location=LOCATION,
        presentation=PRESENTATION,
    )
    return service, session


class CrashRestartFailClosedTests(unittest.TestCase):
    def test_committed_revoke_survives_rebuild_failure_and_process_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "restart.sqlite"
            first, session = make_service(path)
            original_rebuild = first.rebuild_index

            def fail_after_commit():
                raise RuntimeError("simulated process loss after DB commit")

            first.rebuild_index = fail_after_commit
            with self.assertRaisesRegex(RuntimeError, "simulated process loss"):
                first.revoke_session(
                    session.session_id,
                    expected_version=session.version,
                    request_id="restart-after-revoke",
                )

            # The old in-memory generation is already unusable before the
            # simulated process exits.
            self.assertFalse(first.health().ok)
            with self.assertRaises(PersistenceStaleIndexError):
                first.discover(
                    ThoughtGraph.from_dict(minimal_thought("query-before-restart", "thermal")),
                    mode="structural",
                )
            self.assertIsNone(first.public_session_view(session.session_id))
            first.rebuild_index = original_rebuild
            first.repo.close()

            # Startup deterministically rebuilds from the authoritative DB.
            second = LiveCorpusService(SQLiteRepository(path))
            try:
                stored = second.get_session(session.session_id)
                self.assertIsNotNone(stored.revoked_at)
                self.assertFalse(stored.is_discoverable())
                self.assertIsNone(second.public_session_view(session.session_id))
                self.assertIsNone(second.engine.get(stored.thought_id))
                self.assertTrue(second.health().ok)
                self.assertEqual(
                    second.health().db_generation,
                    second.health().serving_generation,
                )
            finally:
                second.repo.close()

    def test_direct_repository_visibility_write_invalidates_serving_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "external.sqlite"
            service, session = make_service(path)
            query = ThoughtGraph.from_dict(minimal_thought("query-external", "thermal"))
            self.assertTrue(service.health().ok)

            hidden = replace(
                session,
                consent=ConsentState(False, False, False, False),
                updated_at="external-write",
            )
            service.repo.put_session(hidden, expected_version=session.version)

            # Even a write that bypasses LiveCorpusService advances the DB
            # generation, so the old engine cannot remain authoritative.
            self.assertFalse(service.health().ok)
            with self.assertRaises(PersistenceStaleIndexError):
                service.discover(query, mode="structural")
            self.assertIsNone(service.public_session_view(session.session_id))

            service.rebuild_index()
            self.assertTrue(service.health().ok)
            self.assertIsNone(service.engine.get(session.thought_id))
            service.repo.close()


if __name__ == "__main__":
    unittest.main()
