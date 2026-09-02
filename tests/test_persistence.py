"""R11-PERSISTENCE: durable store, restart, revoke, metadata invariance."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from demo.corpus.discovery import discover as fixture_discover
from demo.corpus.discovery import is_discoverable, load_sessions
from src.graph import ThoughtGraph
from src.persistence import LiveCorpusService, SQLiteRepository
from src.persistence.errors import PersistenceValidationError
from src.persistence.seed import minimal_thought, seed_pilot_scale, seed_r7
from src.persistence.service import session_to_r7

FLAGSHIP = "ses-aria-plasma-lens"
HIDDEN = "ses-ravi-irrigation"
UNSHARED = "ses-nico-tracing-private"


def file_service(path: Path) -> LiveCorpusService:
    return LiveCorpusService(SQLiteRepository(path))


class MigrationAndHealthTests(unittest.TestCase):
    def test_sqlite_migrates_and_reports_health(self):
        repo = SQLiteRepository(":memory:")
        health = repo.health()
        self.assertTrue(health["ok"])
        self.assertEqual(health["backend"], "sqlite")
        self.assertIn("0001_init", health["migrations"])
        self.assertEqual(health["users"], 0)
        repo.close()

    def test_invalid_thought_dna_is_rejected(self):
        service = LiveCorpusService(SQLiteRepository(":memory:"))
        service.create_user("person-bad", display_label="Bad")
        with self.assertRaises(PersistenceValidationError):
            service.create_session(
                session_id="ses-bad",
                user_id="person-bad",
                thought_dna={"schema_version": "thought-dna/0.1", "thought_id": "x"},
                consent={
                    "share_enabled": True,
                    "share_thought_dna": True,
                    "share_coarse_location": False,
                    "share_display_profile": True,
                },
                location={
                    "kind": "synthetic_coarse",
                    "region": "X",
                    "city": "Y",
                    "lat": 1.0,
                    "lon": 2.0,
                    "precision": "city",
                },
                presentation={"domain": "x", "topic": "y", "cluster_id": "z"},
            )


class R7SeedAndRankingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sessions = load_sessions()
        cls.service = LiveCorpusService(SQLiteRepository(":memory:"))
        seed_r7(cls.service)
        cls.by_id = {s["session_id"]: s for s in cls.sessions}
        cls.query = ThoughtGraph.from_dict(cls.by_id[FLAGSHIP]["thought_dna"])

    def test_seed_round_trip_counts(self):
        self.assertEqual(len(self.service.repo.list_sessions()), len(self.sessions))
        discoverable = [s for s in self.sessions if is_discoverable(s)]
        self.assertEqual(len(self.service.repo.list_discoverable_sessions()), len(discoverable))

    def test_hidden_fixture_sessions_are_not_indexed(self):
        hidden_thought = self.by_id[HIDDEN]["thought_dna"]["thought_id"]
        unshared_thought = self.by_id[UNSHARED]["thought_dna"]["thought_id"]
        self.assertIsNone(self.service.engine.get(hidden_thought))
        self.assertIsNone(self.service.engine.get(unshared_thought))
        self.assertIsNone(self.service.public_session_view(HIDDEN))
        self.assertIsNone(self.service.public_session_view(UNSHARED))

    def test_live_discover_matches_fixture_engine_order(self):
        live = self.service.discover(self.query, mode="analogical", k=20)
        fixture = fixture_discover(
            self.by_id[FLAGSHIP], self.sessions, mode="analogical", k=20
        )
        live_ids = [m["session_id"] for m in live["matches"]]
        fixture_ids = [h["session"]["session_id"] for h in fixture if not h["hard_rejection"]]
        self.assertEqual(live_ids, fixture_ids)
        live_scores = [m["scores"]["structural"] for m in live["matches"]]
        fixture_scores = [h["structural"] for h in fixture if not h["hard_rejection"]]
        self.assertEqual(live_scores, fixture_scores)

    def test_metadata_permutation_cannot_change_scores(self):
        before = self.service.discover(self.query, mode="analogical", k=20)
        before_key = [(m["session_id"], m["mode_classification"], m["scores"]) for m in before["matches"]]
        for session in self.service.repo.list_sessions():
            mutated_pres = {
                "domain": "mutated-domain",
                "topic": "mutated-topic",
                "cluster_id": "mutated-cluster",
            }
            mutated_loc = {
                **dict(session.location),
                "city": "MutantCity",
                "region": "MutantRegion",
                "lat": 12.3,
                "lon": 45.6,
            }
            self.service.update_presentation(
                session.session_id, location=mutated_loc, presentation=mutated_pres
            )
        after = self.service.discover(self.query, mode="analogical", k=20)
        after_key = [(m["session_id"], m["mode_classification"], m["scores"]) for m in after["matches"]]
        self.assertEqual(before_key, after_key)

    def test_aggregation_ignores_hidden_sessions(self):
        resp = self.service.discover(self.query, mode="analogical", k=20)
        blob = json.dumps(resp).lower()
        self.assertNotIn("ravi", blob)
        self.assertNotIn("irrigation", blob)
        self.assertNotIn("tracing-private", blob)


class RestartAndRevokeTests(unittest.TestCase):
    def test_file_backend_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pilot.sqlite"
            first = file_service(path)
            seed_pilot_scale(first, n=100)
            health = first.health()
            self.assertGreaterEqual(health.users, 100)
            self.assertGreaterEqual(health.sessions, 100)
            snapshot = health.engine_snapshot
            first.repo.close()
            second = file_service(path)
            self.assertGreaterEqual(second.health().users, 100)
            self.assertGreaterEqual(second.health().sessions, 100)
            self.assertEqual(second.health().engine_snapshot, snapshot)
            self.assertTrue(second.health().ok)
            second.repo.close()

    def test_revoke_disappears_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pilot.sqlite"
            service = file_service(path)
            seed_r7(service)
            query = ThoughtGraph.from_dict(
                next(s["thought_dna"] for s in load_sessions() if s["session_id"] == FLAGSHIP)
            )
            before = service.discover(query, mode="analogical", k=20)
            target = next(m["session_id"] for m in before["matches"] if m["session_id"] != FLAGSHIP)
            service.revoke_session(target, reason="test-revoke")
            mid = service.discover(query, mode="analogical", k=20)
            mid_ids = {m["session_id"] for m in mid["matches"]} | {m["session_id"] for m in mid["rejected"]}
            self.assertNotIn(target, mid_ids)
            self.assertIsNone(service.public_session_view(target))
            snapshot = service.engine.candidate_index.corpus_snapshot
            service.repo.close()
            restarted = file_service(path)
            after = restarted.discover(query, mode="analogical", k=20)
            after_ids = {m["session_id"] for m in after["matches"]} | {m["session_id"] for m in after["rejected"]}
            self.assertNotIn(target, after_ids)
            self.assertIsNone(restarted.engine.get(
                next(s.thought_id for s in restarted.repo.list_sessions() if s.session_id == target)
            ))
            self.assertEqual(json.dumps(mid, sort_keys=True), json.dumps(after, sort_keys=True))
            self.assertEqual(restarted.engine.candidate_index.corpus_snapshot, snapshot)
            events = [e["event_type"] for e in restarted.audit_log()]
            self.assertIn("session.revoke", events)
            restarted.repo.close()

    def test_hidden_user_absent_from_views(self):
        service = LiveCorpusService(SQLiteRepository(":memory:"))
        seed_r7(service)
        user_id = next(s["person"]["person_id"] for s in load_sessions() if s["session_id"] == FLAGSHIP)
        service.revoke_user(user_id)
        views = {v["session_id"] for v in service.list_public_sessions()}
        owned = [s.session_id for s in service.repo.list_sessions() if s.user_id == user_id]
        for sid in owned:
            self.assertNotIn(sid, views)
            self.assertIsNone(service.public_session_view(sid))

    def test_backup_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "a.sqlite"
            dst = Path(tmp) / "b.sqlite"
            backup = Path(tmp) / "backup.json"
            a = file_service(src)
            seed_r7(a)
            snap = a.health().engine_snapshot
            a.export_backup(backup)
            b = file_service(dst)
            b.import_backup(backup)
            self.assertEqual(b.health().engine_snapshot, snap)
            self.assertEqual(len(b.repo.list_sessions()), len(a.repo.list_sessions()))
            a.repo.close()
            b.repo.close()


class ConcurrencyTests(unittest.TestCase):
    def test_concurrent_create_and_discover(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "conc.sqlite"
            service = file_service(path)
            service.create_user("person-anchor", display_label="Anchor")
            service.create_session(
                session_id="ses-anchor",
                user_id="person-anchor",
                thought_dna=minimal_thought("thought-anchor", "heat"),
                consent={
                    "share_enabled": True,
                    "share_thought_dna": True,
                    "share_coarse_location": True,
                    "share_display_profile": True,
                },
                location={
                    "kind": "synthetic_coarse",
                    "region": "R",
                    "city": "C",
                    "lat": 1.0,
                    "lon": 2.0,
                    "precision": "city",
                },
                presentation={"domain": "d", "topic": "t", "cluster_id": "c"},
            )
            lock = threading.Lock()

            def write(i: int) -> None:
                uid = f"person-c-{i:03d}"
                sid = f"ses-c-{i:03d}"
                tid = f"thought-c-{i:03d}"
                with lock:
                    service.create_user(uid, display_label=f"C{i}")
                    service.create_session(
                        session_id=sid,
                        user_id=uid,
                        thought_dna=minimal_thought(tid, f"heat-{i % 5}"),
                        consent={
                            "share_enabled": True,
                            "share_thought_dna": True,
                            "share_coarse_location": False,
                            "share_display_profile": True,
                        },
                        location={
                            "kind": "synthetic_coarse",
                            "region": "R",
                            "city": "C",
                            "lat": 1.0,
                            "lon": 2.0,
                            "precision": "city",
                        },
                        presentation={"domain": "d", "topic": "t", "cluster_id": "c"},
                        rebuild=False,
                    )

            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(write, range(40)))
            service.rebuild_index()
            query = ThoughtGraph.from_dict(minimal_thought("thought-anchor", "heat"))
            resp = service.discover(query, mode="structural", k=20)
            self.assertIn("matches", resp)
            self.assertGreaterEqual(service.health().sessions, 41)
            service.repo.close()


class IsolationTests(unittest.TestCase):
    def test_persistence_does_not_import_matcher_internals(self):
        root = REPO / "src" / "persistence"
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for banned in ("src.alignment", "src.fingerprint", "src.index.store", "src.scoring"):
                self.assertNotIn(banned, text, path.name)

    def test_r7_converter_keeps_thought_dna_closed(self):
        service = LiveCorpusService(SQLiteRepository(":memory:"))
        seed_r7(service)
        session = service.repo.get_session(FLAGSHIP)
        user = service.repo.get_user(session.user_id)
        record = session_to_r7(session, user)
        for key in ("domain", "topic", "cluster_id", "city", "lat", "lon", "person_id", "session_id"):
            self.assertNotIn(key, record["thought_dna"])


if __name__ == "__main__":
    unittest.main()
