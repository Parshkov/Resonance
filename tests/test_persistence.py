"""R11 persistence recovery acceptance and regression tests.

These tests preserve the useful PR #95 coverage and add the recovery blockers:
DB/index generation fail-closed behavior, immutable ownership, idempotent retry,
optimistic concurrency, and generation-aware readiness.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from demo.corpus.discovery import discover as fixture_discover
from demo.corpus.discovery import is_discoverable, load_sessions
from src.graph import ThoughtGraph
from src.persistence import (
    LiveCorpusService,
    PersistenceConflictError,
    PersistenceOwnershipError,
    PersistenceStaleIndexError,
    PersistenceValidationError,
    SQLiteRepository,
    postgres_available,
)
from src.persistence.factory import open_repository
from src.persistence.seed import minimal_thought, seed_pilot_scale, seed_r7
from src.persistence.service import session_to_r7

FLAGSHIP = "ses-aria-plasma-lens"
HIDDEN = "ses-ravi-irrigation"
UNSHARED = "ses-nico-tracing-private"

DISCOVER = {
    "share_enabled": True,
    "share_thought_dna": True,
    "share_coarse_location": True,
    "share_display_profile": True,
}
HIDE = {
    "share_enabled": False,
    "share_thought_dna": False,
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


def file_service(path: Path) -> LiveCorpusService:
    return LiveCorpusService(SQLiteRepository(path))


def single_service(path=":memory:") -> tuple[LiveCorpusService, object]:
    service = LiveCorpusService(SQLiteRepository(path))
    service.create_user("person-a", display_label="A")
    session = service.create_session(
        session_id="ses-a",
        user_id="person-a",
        thought_dna=minimal_thought("thought-a", "heat"),
        consent=DISCOVER,
        location=LOCATION,
        presentation=PRESENTATION,
    )
    return service, session


class MigrationAndHealthTests(unittest.TestCase):
    def test_clean_sqlite_applies_versioned_recovery_migrations(self):
        repo = SQLiteRepository(":memory:")
        health = repo.health()
        self.assertTrue(health["ok"])
        self.assertEqual(health["backend"], "sqlite")
        self.assertEqual(health["migrations"], ["0001_init", "0002_recovery_generation", "0003_collaboration", "0004_workspaces", "0005_oauth_grants"])
        self.assertEqual(health["corpus_generation"], 0)
        service = LiveCorpusService(repo)
        self.assertTrue(service.health().ok)
        self.assertEqual(service.health().db_generation, service.health().serving_generation)
        repo.close()

    def test_old_0001_database_upgrades_without_rewriting_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.sqlite"
            conn = sqlite3.connect(path)
            old_sql = (REPO / "ops" / "migrations" / "0001_init.sql").read_text()
            conn.executescript(old_sql)
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                ("0001_init", "old"),
            )
            conn.commit()
            conn.close()
            repo = SQLiteRepository(path)
            self.assertEqual(
                repo.health()["migrations"],
                ["0001_init", "0002_recovery_generation", "0003_collaboration", "0004_workspaces", "0005_oauth_grants"],
            )
            columns = {
                row[1] for row in repo._conn.execute("PRAGMA table_info(sessions)").fetchall()
            }
            self.assertIn("version", columns)
            self.assertEqual(repo.get_corpus_generation(), 0)
            repo.close()

    def test_interrupted_sqlite_migration_rolls_back_schema_and_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "interrupted.sqlite"
            conn = sqlite3.connect(path)
            conn.executescript(
                (REPO / "ops" / "migrations" / "0001_init.sql").read_text()
            )
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                ("0001_init", "old"),
            )
            conn.commit()
            conn.close()

            original = SQLiteRepository._record_migration

            def fail_before_marker(repo, version):
                if version == "0002_recovery_generation":
                    raise RuntimeError("simulated loss before migration marker")
                return original(repo, version)

            with patch.object(SQLiteRepository, "_record_migration", fail_before_marker):
                with self.assertRaisesRegex(RuntimeError, "before migration marker"):
                    SQLiteRepository(path)

            conn = sqlite3.connect(path)
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
            }
            markers = {
                row[0] for row in conn.execute("SELECT version FROM schema_migrations")
            }
            conn.close()
            self.assertNotIn("version", columns)
            self.assertEqual(markers, {"0001_init"})

            recovered = SQLiteRepository(path)
            self.assertIn(
                "version",
                {row[1] for row in recovered._conn.execute("PRAGMA table_info(sessions)")},
            )
            self.assertEqual(
                recovered.health()["migrations"],
                ["0001_init", "0002_recovery_generation", "0003_collaboration", "0004_workspaces", "0005_oauth_grants"],
            )
            recovered.close()

    def test_invalid_thought_dna_is_rejected_before_storage(self):
        service = LiveCorpusService(SQLiteRepository(":memory:"))
        service.create_user("person-bad", display_label="Bad")
        before = service.repo.get_corpus_generation()
        with self.assertRaises(PersistenceValidationError):
            service.create_session(
                session_id="ses-bad",
                user_id="person-bad",
                thought_dna={"schema_version": "thought-dna/0.1", "thought_id": "x"},
                consent=DISCOVER,
                location=LOCATION,
                presentation=PRESENTATION,
            )
        self.assertEqual(service.repo.get_corpus_generation(), before)
        self.assertTrue(service.health().ok)

    def test_rebuild_false_makes_readiness_fail_until_rebuilt(self):
        service = LiveCorpusService(SQLiteRepository(":memory:"))
        service.create_user("person-stale", display_label="Stale", rebuild=False)
        health = service.health()
        self.assertFalse(health.ok)
        self.assertFalse(health.index_current)
        with self.assertRaises(PersistenceStaleIndexError):
            service.discover(
                ThoughtGraph.from_dict(minimal_thought("q-stale", "heat")),
                mode="structural",
            )
        service.rebuild_index()
        self.assertTrue(service.health().ok)


class R7SeedAndRankingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sessions = load_sessions()
        cls.service = LiveCorpusService(SQLiteRepository(":memory:"))
        seed_r7(cls.service)
        cls.by_id = {s["session_id"]: s for s in cls.sessions}
        cls.query = ThoughtGraph.from_dict(cls.by_id[FLAGSHIP]["thought_dna"])

    def test_seed_round_trip_counts_and_is_idempotent(self):
        before_versions = {
            s.session_id: s.version for s in self.service.repo.list_sessions(include_deleted=True)
        }
        self.assertEqual(len(before_versions), len(self.sessions))
        discoverable = [s for s in self.sessions if is_discoverable(s)]
        self.assertEqual(len(self.service.repo.list_discoverable_sessions()), len(discoverable))
        seed_r7(self.service)
        after_versions = {
            s.session_id: s.version for s in self.service.repo.list_sessions(include_deleted=True)
        }
        self.assertEqual(before_versions, after_versions)
        self.assertTrue(self.service.health().ok)

    def test_hidden_fixture_sessions_are_not_indexed_or_public(self):
        hidden_thought = self.by_id[HIDDEN]["thought_dna"]["thought_id"]
        unshared_thought = self.by_id[UNSHARED]["thought_dna"]["thought_id"]
        self.assertIsNone(self.service.engine.get(hidden_thought))
        self.assertIsNone(self.service.engine.get(unshared_thought))
        self.assertIsNone(self.service.public_session_view(HIDDEN))
        self.assertIsNone(self.service.public_session_view(UNSHARED))

    def test_live_discovery_preserves_accepted_fixture_order_and_scores(self):
        live = self.service.discover(self.query, mode="analogical", k=20)
        fixture = fixture_discover(
            self.by_id[FLAGSHIP], self.sessions, mode="analogical", k=20
        )
        live_ids = [m["session_id"] for m in live["matches"]]
        fixture_ids = [
            h["session"]["session_id"] for h in fixture if not h["hard_rejection"]
        ]
        self.assertEqual(live_ids, fixture_ids)
        self.assertEqual(
            [m["scores"]["structural"] for m in live["matches"]],
            [h["structural"] for h in fixture if not h["hard_rejection"]],
        )

    def test_metadata_permutation_cannot_change_matching(self):
        before = self.service.discover(self.query, mode="analogical", k=20)
        before_key = [
            (m["session_id"], m["mode_classification"], m["scores"])
            for m in before["matches"]
        ]
        for session in self.service.repo.list_sessions():
            self.service.update_presentation(
                session.session_id,
                location={**dict(session.location), "city": "Mutant", "lat": 12.3, "lon": 45.6},
                presentation={"domain": "mutated", "topic": "mutated", "cluster_id": "mutated"},
                expected_version=session.version,
                rebuild=False,
            )
        self.assertFalse(self.service.health().ok)
        self.service.rebuild_index()
        after = self.service.discover(self.query, mode="analogical", k=20)
        after_key = [
            (m["session_id"], m["mode_classification"], m["scores"])
            for m in after["matches"]
        ]
        self.assertEqual(before_key, after_key)

    def test_aggregation_ignores_hidden_sessions(self):
        blob = json.dumps(self.service.discover(self.query, mode="analogical", k=20)).lower()
        self.assertNotIn("ravi", blob)
        self.assertNotIn("irrigation", blob)
        self.assertNotIn("tracing-private", blob)


class GenerationFailClosedTests(unittest.TestCase):
    def _post_commit_rebuild_failure(self, mutation):
        service, session = single_service()
        original_rebuild = service.rebuild_index

        def fail_rebuild():
            raise RuntimeError("injected rebuild failure")

        service.rebuild_index = fail_rebuild
        with self.assertRaisesRegex(RuntimeError, "injected rebuild failure"):
            mutation(service, session)

        self.assertFalse(service.health().ok)
        self.assertFalse(service.health().index_current)
        self.assertIsNone(service.public_session_view(session.session_id))
        with self.assertRaises(PersistenceStaleIndexError):
            service.discover(
                ThoughtGraph.from_dict(minimal_thought("q", "heat")),
                mode="structural",
            )
        service.rebuild_index = original_rebuild
        service.rebuild_index()
        self.assertTrue(service.health().ok)
        return service

    def test_consent_disable_cannot_leak_if_rebuild_fails_after_commit(self):
        service = self._post_commit_rebuild_failure(
            lambda svc, session: svc.update_consent(
                session.session_id,
                HIDE,
                expected_version=session.version,
                request_id="consent-disable-1",
            )
        )
        self.assertFalse(service.get_session("ses-a").is_discoverable())

    def test_revoke_cannot_leak_if_rebuild_fails_after_commit(self):
        service = self._post_commit_rebuild_failure(
            lambda svc, session: svc.revoke_session(
                session.session_id,
                expected_version=session.version,
                request_id="revoke-1",
            )
        )
        self.assertIsNotNone(service.get_session("ses-a").revoked_at)

    def test_delete_cannot_leak_if_rebuild_fails_after_commit(self):
        service = self._post_commit_rebuild_failure(
            lambda svc, session: svc.delete_session(
                session.session_id,
                expected_version=session.version,
                request_id="delete-1",
            )
        )
        self.assertIsNotNone(service.get_session("ses-a").deleted_at)

    def test_retry_after_commit_before_rebuild_is_single_mutation_and_heals(self):
        service, session = single_service()
        original_rebuild = service.rebuild_index
        calls = [0]

        def fail_once():
            calls[0] += 1
            if calls[0] == 1:
                raise RuntimeError("timeout after commit")
            return original_rebuild()

        service.rebuild_index = fail_once
        with self.assertRaisesRegex(RuntimeError, "timeout after commit"):
            service.revoke_session(
                session.session_id,
                expected_version=session.version,
                request_id="retry-revoke-1",
            )
        committed = service.get_session(session.session_id)
        committed_version = committed.version
        self.assertEqual(committed_version, session.version + 1)
        replay = service.revoke_session(
            session.session_id,
            expected_version=session.version,
            request_id="retry-revoke-1",
        )
        self.assertEqual(replay.version, committed_version)
        self.assertTrue(service.health().ok)
        events = [e for e in service.audit_log() if e["event_type"] == "session.revoke"]
        self.assertEqual(len(events), 1)


class OwnershipConcurrencyAndRetryTests(unittest.TestCase):
    def test_stale_profile_upsert_cannot_clear_committed_user_revocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "user-revoke-race.sqlite"
            first = file_service(path)
            first.create_user("person-race", display_label="Before")
            stale = first.get_user("person-race")
            second = SQLiteRepository(path)
            second.put_user(
                replace(stale, revoked_at="committed-revoke", updated_at="newer")
            )

            stored = first.repo.put_user(
                replace(
                    stale,
                    display_label="Stale writer",
                    updated_at="stale-later-write",
                    revoked_at=None,
                )
            )
            self.assertEqual(stored.revoked_at, "committed-revoke")
            self.assertEqual(
                first.repo.get_user("person-race").revoked_at,
                "committed-revoke",
            )
            second.close()
            first.repo.close()

    def test_user_create_request_id_replays_one_committed_mutation(self):
        service = LiveCorpusService(SQLiteRepository(":memory:"))
        first = service.create_user(
            "person-retry-user",
            display_label="Retry User",
            request_id="user-create-once",
        )
        generation = service.repo.get_corpus_generation()
        replay = service.create_user(
            "person-retry-user",
            display_label="Retry User",
            request_id="user-create-once",
        )
        self.assertEqual(replay, first)
        self.assertEqual(service.repo.get_corpus_generation(), generation)
        self.assertEqual(
            len([e for e in service.audit_log() if e["event_type"] == "user.upsert"]),
            1,
        )
        with self.assertRaises(PersistenceConflictError):
            service.create_user(
                "person-retry-user",
                display_label="Different payload",
                request_id="user-create-once",
            )

    def test_user_revoke_retry_heals_after_committed_rebuild_failure(self):
        service, session = single_service()
        original_rebuild = service.rebuild_index
        calls = [0]

        def fail_once():
            calls[0] += 1
            if calls[0] == 1:
                raise RuntimeError("timeout after committed user revoke")
            return original_rebuild()

        service.rebuild_index = fail_once
        with self.assertRaisesRegex(RuntimeError, "committed user revoke"):
            service.revoke_user("person-a", request_id="user-revoke-once")
        generation = service.repo.get_corpus_generation()
        self.assertIsNotNone(service.get_user("person-a").revoked_at)
        self.assertIsNotNone(service.get_session(session.session_id).revoked_at)
        self.assertFalse(service.health().ok)

        replay = service.revoke_user("person-a", request_id="user-revoke-once")
        self.assertIsNotNone(replay.revoked_at)
        self.assertEqual(service.repo.get_corpus_generation(), generation)
        self.assertTrue(service.health().ok)
        self.assertEqual(
            len([e for e in service.audit_log() if e["event_type"] == "user.revoke"]),
            1,
        )
        self.assertEqual(
            len([e for e in service.audit_log() if e["event_type"] == "session.revoke"]),
            1,
        )

    def test_session_ownership_is_immutable_at_repository_boundary(self):
        service, stored = single_service()
        service.create_user("person-b", display_label="B")
        stolen = replace(stored, user_id="person-b", updated_at="later")
        before_generation = service.repo.get_corpus_generation()
        with self.assertRaises(PersistenceOwnershipError):
            service.repo.put_session(stolen, expected_version=stored.version)
        after = service.get_session(stored.session_id)
        self.assertEqual(after.user_id, "person-a")
        self.assertEqual(after.version, stored.version)
        self.assertEqual(service.repo.get_corpus_generation(), before_generation)

    def test_service_rejects_conflicting_owner_upsert(self):
        service, stored = single_service()
        service.create_user("person-b", display_label="B")
        with self.assertRaises(PersistenceOwnershipError):
            service.create_session(
                session_id=stored.session_id,
                user_id="person-b",
                thought_dna=stored.thought_dna,
                consent=stored.consent,
                location=stored.location,
                presentation=stored.presentation,
                expected_version=stored.version,
            )
        self.assertEqual(service.get_session(stored.session_id).user_id, "person-a")

    def test_stale_expected_version_fails_without_generation_change(self):
        service, stored = single_service()
        newer = service.update_consent(
            stored.session_id,
            HIDE,
            expected_version=stored.version,
            request_id="version-advance",
        )
        before_generation = service.repo.get_corpus_generation()
        with self.assertRaises(PersistenceConflictError):
            service.update_presentation(
                stored.session_id,
                presentation={"domain": "stale"},
                expected_version=stored.version,
            )
        self.assertEqual(service.get_session(stored.session_id).version, newer.version)
        self.assertEqual(service.repo.get_corpus_generation(), before_generation)
        self.assertTrue(service.health().ok)

    def test_duplicate_request_id_different_payload_is_rejected(self):
        service, stored = single_service()
        service.update_consent(
            stored.session_id,
            HIDE,
            expected_version=stored.version,
            request_id="same-key",
        )
        before = service.repo.get_corpus_generation()
        with self.assertRaises(PersistenceConflictError):
            service.update_consent(
                stored.session_id,
                DISCOVER,
                expected_version=stored.version,
                request_id="same-key",
            )
        self.assertEqual(service.repo.get_corpus_generation(), before)

    def test_idempotent_result_survives_process_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "retry.sqlite"
            first, stored = single_service(path)
            result = first.revoke_session(
                stored.session_id,
                expected_version=stored.version,
                request_id="restart-retry",
            )
            generation = first.repo.get_corpus_generation()
            first.repo.close()

            second = file_service(path)
            replay = second.revoke_session(
                stored.session_id,
                expected_version=stored.version,
                request_id="restart-retry",
            )
            self.assertEqual(replay.version, result.version)
            self.assertEqual(second.repo.get_corpus_generation(), generation)
            self.assertEqual(
                len([e for e in second.audit_log() if e["event_type"] == "session.revoke"]),
                1,
            )
            self.assertTrue(second.health().ok)
            second.repo.close()


class RestartBackupAndScaleTests(unittest.TestCase):
    def test_100_users_sessions_survive_restart_with_identical_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pilot.sqlite"
            first = file_service(path)
            seed_pilot_scale(first, n=100)
            health = first.health()
            self.assertGreaterEqual(health.users, 100)
            self.assertGreaterEqual(health.sessions, 100)
            snapshot = health.engine_snapshot
            generation = health.db_generation
            first.repo.close()

            second = file_service(path)
            self.assertGreaterEqual(second.health().users, 100)
            self.assertGreaterEqual(second.health().sessions, 100)
            self.assertEqual(second.health().engine_snapshot, snapshot)
            self.assertEqual(second.health().db_generation, generation)
            self.assertEqual(second.health().serving_generation, generation)
            self.assertTrue(second.health().ok)
            second.repo.close()

    def test_revoke_disappears_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pilot.sqlite"
            service = file_service(path)
            seed_r7(service)
            by_id = {s["session_id"]: s for s in load_sessions()}
            query = ThoughtGraph.from_dict(by_id[FLAGSHIP]["thought_dna"])
            before = service.discover(query, mode="analogical", k=20)
            target = next(
                m["session_id"] for m in before["matches"] if m["session_id"] != FLAGSHIP
            )
            target_row = service.get_session(target)
            service.revoke_session(
                target,
                expected_version=target_row.version,
                request_id="restart-target-revoke",
            )
            mid = service.discover(query, mode="analogical", k=20)
            mid_ids = {m["session_id"] for m in mid["matches"]} | {
                m["session_id"] for m in mid["rejected"]
            }
            self.assertNotIn(target, mid_ids)
            self.assertIsNone(service.public_session_view(target))
            snapshot = service.health().engine_snapshot
            service.repo.close()

            restarted = file_service(path)
            after = restarted.discover(query, mode="analogical", k=20)
            after_ids = {m["session_id"] for m in after["matches"]} | {
                m["session_id"] for m in after["rejected"]
            }
            self.assertNotIn(target, after_ids)
            self.assertEqual(json.dumps(mid, sort_keys=True), json.dumps(after, sort_keys=True))
            self.assertEqual(restarted.health().engine_snapshot, snapshot)
            restarted.repo.close()

    def test_hidden_user_absent_from_views_and_rebuilt_index(self):
        service = LiveCorpusService(SQLiteRepository(":memory:"))
        seed_r7(service)
        user_id = next(
            s["person"]["person_id"] for s in load_sessions() if s["session_id"] == FLAGSHIP
        )
        service.revoke_user(user_id)
        views = {v["session_id"] for v in service.list_public_sessions()}
        owned = [s for s in service.repo.list_sessions() if s.user_id == user_id]
        for session in owned:
            self.assertNotIn(session.session_id, views)
            self.assertIsNone(service.public_session_view(session.session_id))
            self.assertIsNone(service.engine.get(session.thought_id))

    def test_backup_round_trip_preserves_versions_and_structural_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "a.sqlite"
            dst = Path(tmp) / "b.sqlite"
            backup = Path(tmp) / "backup.json"
            a = file_service(src)
            seed_r7(a)
            target = a.get_session(FLAGSHIP)
            a.update_presentation(
                FLAGSHIP,
                presentation={"domain": "changed", "topic": "t", "cluster_id": "c"},
                expected_version=target.version,
                request_id="backup-version",
            )
            version = a.get_session(FLAGSHIP).version
            snap = a.health().engine_snapshot
            a.export_backup(backup)

            b = file_service(dst)
            b.import_backup(backup)
            self.assertEqual(b.get_session(FLAGSHIP).version, version)
            self.assertEqual(b.health().engine_snapshot, snap)
            self.assertEqual(len(b.repo.list_sessions()), len(a.repo.list_sessions()))
            self.assertTrue(b.health().ok)
            a.repo.close()
            b.repo.close()

    def test_concurrent_create_and_discover_smoke(self):
        service = LiveCorpusService(SQLiteRepository(":memory:"))
        for i in range(12):
            service.create_user(f"person-c-{i:03d}", display_label=f"C{i}", rebuild=False)
        service.rebuild_index()
        query = ThoughtGraph.from_dict(minimal_thought("query-concurrent", "heat"))

        def write(i: int):
            return service.create_session(
                session_id=f"ses-c-{i:03d}",
                user_id=f"person-c-{i:03d}",
                thought_dna=minimal_thought(f"thought-c-{i:03d}", f"heat-{i % 4}"),
                consent=DISCOVER,
                location=LOCATION,
                presentation=PRESENTATION,
            )

        def read(_i: int):
            return service.discover(query, mode="structural", k=8)

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = []
            for i in range(12):
                futures.append(pool.submit(write, i))
                futures.append(pool.submit(read, i))
            results = [f.result() for f in futures]
        self.assertTrue(any(isinstance(r, dict) and "matches" in r for r in results))
        self.assertEqual(service.health().sessions, 12)
        self.assertTrue(service.health().ok)


class IsolationAndBackendTests(unittest.TestCase):
    def test_persistence_does_not_import_matcher_implementation_internals(self):
        root = REPO / "src" / "persistence"
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for banned in (
                "src.alignment",
                "src.fingerprint",
                "src.index.store",
                "src.scoring",
                "solve_fgw",
                "adjudicate(",
            ):
                self.assertNotIn(banned, text, path.name)

    def test_r7_converter_keeps_metadata_outside_thought_dna(self):
        service = LiveCorpusService(SQLiteRepository(":memory:"))
        seed_r7(service)
        session = service.get_session(FLAGSHIP)
        user = service.get_user(session.user_id)
        record = session_to_r7(session, user)
        for key in (
            "domain",
            "topic",
            "cluster_id",
            "city",
            "lat",
            "lon",
            "person_id",
            "session_id",
        ):
            self.assertNotIn(key, record["thought_dna"])

    def test_postgres_dsn_never_silently_falls_back_to_sqlite(self):
        if postgres_available():
            self.skipTest("PostgreSQL driver installed; live connection needs test DSN")
        with self.assertRaises(RuntimeError):
            open_repository("postgresql://localhost/resonance")

    @unittest.skipUnless(
        os.environ.get("RESONANCE_TEST_POSTGRES_URL") and postgres_available(),
        "set RESONANCE_TEST_POSTGRES_URL with an isolated test DB for live PostgreSQL smoke",
    )
    def test_live_postgres_generation_ownership_and_restart_smoke(self):
        repo = open_repository(os.environ["RESONANCE_TEST_POSTGRES_URL"])
        service = LiveCorpusService(repo)
        try:
            service.reset()
            service.create_user("person-pg", display_label="PG")
            stored = service.create_session(
                session_id="ses-pg",
                user_id="person-pg",
                thought_dna=minimal_thought("thought-pg", "heat"),
                consent=DISCOVER,
                location=LOCATION,
                presentation=PRESENTATION,
                request_id="pg-create",
            )
            self.assertEqual(stored.version, 1)
            self.assertTrue(service.health().ok)
            service.create_user("person-pg-other", display_label="Other")
            with self.assertRaises(PersistenceOwnershipError):
                service.create_session(
                    session_id="ses-pg",
                    user_id="person-pg-other",
                    thought_dna=stored.thought_dna,
                    consent=DISCOVER,
                    location=LOCATION,
                    presentation=PRESENTATION,
                    expected_version=stored.version,
                )
        finally:
            service.reset()
            repo.close()


if __name__ == "__main__":
    unittest.main()
