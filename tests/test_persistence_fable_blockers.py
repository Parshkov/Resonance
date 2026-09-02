"""Regressions for the independent Fable review of R11 recovery.

These tests are intentionally adversarial: duplicate Thought DNA ownership,
tombstone re-share, malformed location shapes, and restart repairability.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from src.graph import ThoughtGraph
from src.persistence import (
    LiveCorpusService,
    PersistenceConflictError,
    PersistenceStaleIndexError,
    PersistenceValidationError,
    SQLiteRepository,
)
from src.persistence.seed import minimal_thought

DISCOVER = {
    "share_enabled": True,
    "share_thought_dna": True,
    "share_coarse_location": True,
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
PRESENTATION = {"domain": "test", "topic": "hardening", "cluster_id": "r11"}


def seeded(path=":memory:"):
    service = LiveCorpusService(SQLiteRepository(path))
    service.create_user("person-a", display_label="A")
    service.create_user("person-b", display_label="B")
    first = service.create_session(
        session_id="ses-a",
        user_id="person-a",
        thought_dna=minimal_thought("thought-a", "heat"),
        consent=DISCOVER,
        location=LOCATION,
        presentation=PRESENTATION,
    )
    return service, first


class ThoughtUniquenessBoundaryTests(unittest.TestCase):
    def test_cross_user_duplicate_thought_is_typed_conflict_and_keeps_index_current(self):
        service, first = seeded()
        generation = service.repo.get_corpus_generation()
        with self.assertRaises(PersistenceConflictError):
            service.create_session(
                session_id="ses-b",
                user_id="person-b",
                thought_dna=first.thought_dna,
                consent=DISCOVER,
                location=LOCATION,
                presentation=PRESENTATION,
            )
        self.assertEqual(service.repo.get_corpus_generation(), generation)
        self.assertIsNone(service.get_session("ses-b"))
        self.assertTrue(service.health().ok)

    def test_direct_sqlite_repository_unique_failure_is_never_raw_integrity_error(self):
        service, first = seeded()
        duplicate = replace(
            first,
            session_id="ses-b",
            user_id="person-b",
            version=0,
        )
        with self.assertRaises(PersistenceConflictError):
            service.repo.put_session(duplicate)
        self.assertTrue(service.health().ok)

    def test_deleted_thought_id_is_permanently_reserved_for_v01(self):
        service, first = seeded()
        service.delete_session(
            first.session_id,
            expected_version=first.version,
            request_id="delete-a",
        )
        generation = service.repo.get_corpus_generation()
        with self.assertRaisesRegex(PersistenceConflictError, "new Thought DNA id"):
            service.create_session(
                session_id="ses-a-reborn",
                user_id="person-a",
                thought_dna=first.thought_dna,
                consent=DISCOVER,
                location=LOCATION,
                presentation=PRESENTATION,
            )
        self.assertEqual(service.repo.get_corpus_generation(), generation)
        self.assertTrue(service.health().ok)


class ProjectionValidationAndRestartTests(unittest.TestCase):
    def test_malformed_location_is_rejected_before_durable_write(self):
        service = LiveCorpusService(SQLiteRepository(":memory:"))
        service.create_user("person-a", display_label="A")
        before = service.repo.get_corpus_generation()
        bad = {"city": "Moscow", "lat": 55.8, "lon": 37.6}
        with self.assertRaises(PersistenceValidationError):
            service.create_session(
                session_id="ses-bad",
                user_id="person-a",
                thought_dna=minimal_thought("thought-bad", "heat"),
                consent=DISCOVER,
                location=bad,
                presentation=PRESENTATION,
            )
        self.assertEqual(service.repo.get_corpus_generation(), before)
        self.assertIsNone(service.get_session("ses-bad"))
        self.assertTrue(service.health().ok)

    def test_unknown_precise_location_field_is_rejected(self):
        service = LiveCorpusService(SQLiteRepository(":memory:"))
        service.create_user("person-a", display_label="A")
        bad = {**LOCATION, "raw_point": {"lat": 10.012345, "lon": 20.012345}}
        with self.assertRaisesRegex(PersistenceValidationError, "unknown fields"):
            service.create_session(
                session_id="ses-bad-extra",
                user_id="person-a",
                thought_dna=minimal_thought("thought-bad-extra", "heat"),
                consent=DISCOVER,
                location=bad,
                presentation=PRESENTATION,
            )

    def test_restart_with_legacy_bad_row_stays_bootable_fail_closed_and_repairable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad-location.sqlite"
            first, session = seeded(path)
            first.repo.close()

            # Simulate a pre-hardening durable row that already committed.
            conn = sqlite3.connect(path)
            conn.execute(
                "UPDATE sessions SET location_json = ? WHERE session_id = ?",
                (json.dumps({"city": "Moscow", "lat": 55.8, "lon": 37.6}), session.session_id),
            )
            conn.execute(
                "UPDATE persistence_state SET corpus_generation = corpus_generation + 1 WHERE state_id = 1"
            )
            conn.commit()
            conn.close()

            restarted = LiveCorpusService(SQLiteRepository(path))
            try:
                self.assertFalse(restarted.health().ok)
                self.assertFalse(restarted.health().index_current)
                self.assertIn("not R7-projectable", restarted.health().details["degraded_reason"])
                with self.assertRaises(PersistenceStaleIndexError):
                    restarted.discover(
                        ThoughtGraph.from_dict(minimal_thought("query-bad", "heat")),
                        mode="structural",
                    )

                stored = restarted.get_session(session.session_id)
                repaired = restarted.update_presentation(
                    stored.session_id,
                    location=LOCATION,
                    presentation=PRESENTATION,
                    expected_version=stored.version,
                )
                self.assertGreater(repaired.version, stored.version)
                self.assertTrue(restarted.health().ok)
                self.assertTrue(restarted.health().index_current)
            finally:
                restarted.repo.close()


if __name__ == "__main__":
    unittest.main()
