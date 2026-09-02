"""Focused R11 regressions for the R12C private-draft alignment review."""

from __future__ import annotations

import unittest

from src.persistence import (
    LiveCorpusService,
    PersistenceConflictError,
    PersistenceValidationError,
    SQLiteRepository,
)
from src.persistence.seed import minimal_thought

PRIVATE = {
    "share_enabled": False,
    "share_thought_dna": False,
    "share_coarse_location": False,
    "share_display_profile": False,
}
DISCOVER = {
    "share_enabled": True,
    "share_thought_dna": True,
    "share_coarse_location": False,
    "share_display_profile": False,
}
LOCATION = {
    "kind": "synthetic_coarse",
    "region": "R",
    "city": "C",
    "lat": 1.0,
    "lon": 2.0,
    "precision": "city",
}
PRESENTATION = {"domain": "d", "topic": "t", "cluster_id": "c"}


class PrivateSparseDraftAlignmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = LiveCorpusService(SQLiteRepository(":memory:"))
        self.service.create_user("person-a", display_label="A")

    def tearDown(self) -> None:
        self.service.repo.close()

    def test_private_session_may_omit_location_and_presentation(self):
        stored = self.service.create_session(
            session_id="ses-private",
            user_id="person-a",
            thought_dna=minimal_thought("thought-private", "heat"),
            consent=PRIVATE,
            location={},
            presentation={},
        )
        self.assertEqual(dict(stored.location), {})
        self.assertEqual(dict(stored.presentation), {})
        self.assertTrue(self.service.health().ok)

    def test_discoverable_transition_requires_complete_projection(self):
        stored = self.service.create_session(
            session_id="ses-private",
            user_id="person-a",
            thought_dna=minimal_thought("thought-private", "heat"),
            consent=PRIVATE,
            location={},
            presentation={},
        )
        with self.assertRaises(PersistenceValidationError):
            self.service.update_consent(
                stored.session_id,
                DISCOVER,
                expected_version=stored.version,
            )
        self.assertFalse(self.service.get_session(stored.session_id).is_discoverable())
        self.assertTrue(self.service.health().ok)

    def test_stale_metadata_version_wins_before_replacement_shape_validation(self):
        stored = self.service.create_session(
            session_id="ses-full",
            user_id="person-a",
            thought_dna=minimal_thought("thought-full", "heat"),
            consent=DISCOVER,
            location=LOCATION,
            presentation=PRESENTATION,
        )
        newer = self.service.update_consent(
            stored.session_id,
            PRIVATE,
            expected_version=stored.version,
        )
        before_generation = self.service.repo.get_corpus_generation()
        with self.assertRaises(PersistenceConflictError):
            self.service.update_presentation(
                stored.session_id,
                presentation={"domain": "stale"},
                expected_version=stored.version,
            )
        self.assertEqual(self.service.get_session(stored.session_id).version, newer.version)
        self.assertEqual(self.service.repo.get_corpus_generation(), before_generation)
        self.assertTrue(self.service.health().ok)

    def test_metadata_request_id_replays_before_stale_version_and_rejects_collision(self):
        stored = self.service.create_session(
            session_id="ses-idempotent-meta",
            user_id="person-a",
            thought_dna=minimal_thought("thought-idempotent-meta", "heat"),
            consent=DISCOVER,
            location=LOCATION,
            presentation=PRESENTATION,
        )
        updated_presentation = {
            "domain": "updated",
            "topic": "updated",
            "cluster_id": "updated",
        }
        first = self.service.update_presentation(
            stored.session_id,
            presentation=updated_presentation,
            expected_version=stored.version,
            request_id="meta-key-1",
        )
        generation = self.service.repo.get_corpus_generation()

        replay = self.service.update_presentation(
            stored.session_id,
            presentation=updated_presentation,
            expected_version=stored.version,
            request_id="meta-key-1",
        )
        self.assertEqual(replay.version, first.version)
        self.assertEqual(dict(replay.presentation), updated_presentation)
        self.assertEqual(self.service.repo.get_corpus_generation(), generation)

        with self.assertRaises(PersistenceConflictError):
            self.service.update_presentation(
                stored.session_id,
                presentation={
                    "domain": "different",
                    "topic": "updated",
                    "cluster_id": "updated",
                },
                expected_version=stored.version,
                request_id="meta-key-1",
            )
        self.assertEqual(self.service.repo.get_corpus_generation(), generation)


if __name__ == "__main__":
    unittest.main()
