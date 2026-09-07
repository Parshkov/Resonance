"""Emptying a deployment that was only ever tested in.

Before anyone real arrives, a live deployment holds the residue of proving it
works: thoughts written to exercise a path, the alerts they raised against each
other, an introduction accepted to show introductions work. To the first person
who arrives that is indistinguishable from a world where other people are
thinking, and the resonance they are shown is with a test.

These tests pin what the one-shot operator action removes, and — more
importantly — what it must leave standing, because an emptied corpus that also
signs everyone out and disconnects every MCP client is a worse outcome than the
residue.
"""

from __future__ import annotations

import unittest

from src.product import server as product_server
from src.product.server import build_runtime
from src.product.standing import ALERT_KIND

ORIGINS = frozenset({"http://127.0.0.1"})


def _runtime():
    return build_runtime(":ephemeral:", allowed_origins=ORIGINS)


def _an_alert(runtime, user_id: str, mine: str, theirs: str) -> str:
    key = f"{user_id}|{mine}|{theirs}"
    runtime.live.repo.put_grant(ALERT_KIND, key, {
        "alert_key": key,
        "user_id": user_id,
        "my_session_id": mine,
        "their_session_id": theirs,
        "mode": "analogical",
        "scores_at_detection": {},
        "detected_at": "2026-01-01T00:00:00Z",
        "reason": "you_shared",
        "seen_at": None,
    }, user_id=user_id)
    return key


def _an_accepted_intro(runtime, a: str, b: str) -> None:
    """A durable intro, its channel and one message, written the way the rows
    exist after two people were actually introduced."""
    repo = runtime.live.repo
    repo._execute(
        "INSERT INTO intros(intro_id, from_session_id, to_session_id, from_user_id, "
        "to_user_id, state, message, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 'accepted', '', ?, ?)",
        ("intro-test", a, b, "person-a", "person-b", "2026-01-01T00:00:00Z",
         "2026-01-01T00:00:00Z"))
    repo._execute(
        "INSERT INTO channels(channel_id, intro_id, created_at) VALUES (?, ?, ?)",
        ("chan-test", "intro-test", "2026-01-01T00:00:00Z"))
    repo._execute(
        "INSERT INTO messages(message_id, channel_id, author_user_id, body, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("msg-test", "chan-test", "person-a", "hello", "2026-01-01T00:00:00Z"))
    repo._conn.commit()


class PurgeCorpusTests(unittest.TestCase):
    def test_unset_or_unrecognised_does_nothing_at_all(self):
        runtime = _runtime()
        try:
            before = product_server.corpus_summary(runtime)["sessions_by_kind"]
            self.assertIsNone(product_server.startup_purge_corpus(runtime, {}))
            self.assertIsNone(product_server.startup_purge_corpus(
                runtime, {"RESONANCE_PURGE_CORPUS": ""}))
            self.assertIsNone(product_server.startup_purge_corpus(
                runtime, {"RESONANCE_PURGE_CORPUS": "maybe"}))
            self.assertEqual(product_server.corpus_summary(runtime)["sessions_by_kind"], before)
        finally:
            runtime.live.repo.close()

    def test_report_counts_without_changing_anything(self):
        runtime = _runtime()
        try:
            ids = [s.session_id for s in runtime.live.repo.list_sessions()]
            _an_alert(runtime, "person-gone", ids[0], ids[1])
            _an_accepted_intro(runtime, ids[0], ids[1])

            result = product_server.startup_purge_corpus(
                runtime, {"RESONANCE_PURGE_CORPUS": "report"})
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["sessions_to_delete"], len(ids))
            self.assertEqual(result["connections_to_delete"]["intros"], 1)
            self.assertEqual(result["connections_to_delete"]["messages"], 1)
            # The report says what the applied run WILL retract. It once said
            # zero here whatever the store held, because it only ever counted
            # while deleting -- so an operator read "no alerts" off a store
            # with six in it.
            self.assertEqual(result["alerts_to_retract"], 1)
            self.assertEqual(result["alerts_retracted"], 0)

            # nothing moved
            self.assertEqual(len([s for s in runtime.live.repo.list_sessions()
                                  if s.deleted_at is None]), len(ids))
            self.assertIsNotNone(runtime.live.repo.get_grant(
                ALERT_KIND, f"person-gone|{ids[0]}|{ids[1]}"))
        finally:
            runtime.live.repo.close()

    def test_applied_empties_the_corpus_and_leaves_accounts_and_oauth_standing(self):
        runtime = _runtime()
        try:
            repo = runtime.live.repo
            ids = [s.session_id for s in repo.list_sessions()]
            users_before = len(repo.list_users())
            self.assertGreater(users_before, 0)
            # Deliberately owned by an account that is not in `users`: this is
            # what an alert looks like after its owner was revoked, and walking
            # live accounts would never reach it.
            _an_alert(runtime, "person-gone", ids[0], ids[1])
            _an_alert(runtime, repo.get_session(ids[0]).user_id, ids[0], ids[1])
            _an_accepted_intro(runtime, ids[0], ids[1])
            # An OAuth registration is what a connected MCP client authorized
            # with. Wiping it would make every client re-authorize, which is
            # the whole reason this is not `reset`.
            repo.put_grant("client_registration", "client-test",
                           {"client_id": "client-test"}, user_id="person-a")

            result = product_server.startup_purge_corpus(
                runtime, {"RESONANCE_PURGE_CORPUS": "1"})
            self.assertFalse(result["dry_run"])
            self.assertEqual(result["sessions_to_delete"], len(ids))
            self.assertEqual(result["alerts_to_retract"], 2)
            self.assertEqual(result["alerts_retracted"], 2)
            self.assertEqual(result["connections_deleted"]["intros"], 1)

            summary = product_server.corpus_summary(runtime)
            self.assertEqual(summary["sessions_by_kind"], {})
            self.assertEqual(summary["volunteer_sessions"], 0)
            self.assertEqual(repo._fetchone_map("SELECT COUNT(*) AS n FROM intros")["n"], 0)
            self.assertEqual(repo._fetchone_map("SELECT COUNT(*) AS n FROM messages")["n"], 0)
            self.assertIsNone(repo.get_grant(ALERT_KIND, f"person-gone|{ids[0]}|{ids[1]}"))

            # what must survive
            self.assertEqual(len(repo.list_users()), users_before)
            self.assertIsNotNone(repo.get_grant("client_registration", "client-test"))
            self.assertTrue(runtime.live.health().ok)
            self.assertTrue(runtime.live.health().index_current)
        finally:
            runtime.live.repo.close()

    def test_a_second_run_finds_nothing_left_to_do(self):
        runtime = _runtime()
        try:
            product_server.startup_purge_corpus(runtime, {"RESONANCE_PURGE_CORPUS": "1"})
            again = product_server.startup_purge_corpus(
                runtime, {"RESONANCE_PURGE_CORPUS": "1"})
            self.assertEqual(again["sessions_to_delete"], 0)
            self.assertEqual(again["alerts_retracted"], 0)
            self.assertEqual(sum(again["connections_deleted"].values()), 0)
            self.assertTrue(runtime.live.health().ok)
        finally:
            runtime.live.repo.close()

    def test_keep_is_refused_rather_than_ignored(self):
        # An operator who set KEEP expects something to survive. Ignoring it
        # would delete their exception and tell them afterwards.
        runtime = _runtime()
        try:
            ids = [s.session_id for s in runtime.live.repo.list_sessions()]
            result = product_server.startup_purge_corpus(
                runtime, {"RESONANCE_PURGE_CORPUS": "1", "RESONANCE_PURGE_KEEP": ids[0]})
            self.assertIn("refused", result)
            self.assertEqual(len([s for s in runtime.live.repo.list_sessions()
                                  if s.deleted_at is None]), len(ids))
        finally:
            runtime.live.repo.close()


class TheFirstPersonInAnEmptyWorldTests(unittest.TestCase):
    """What the purge leaves behind is the state every deployment starts in,
    and the one nobody had ever run: a corpus with nothing in it.

    Emptying production would be a poor trade if the first person to arrive
    afterwards hit an error, or was told something that reads as a failure.
    """

    def test_discovery_answers_on_an_empty_corpus_without_calling_it_a_failure(self):
        from src.graph import ThoughtGraph
        from src.persistence.seed import minimal_thought
        from src.product import phrasing

        runtime = _runtime()
        try:
            product_server.startup_purge_corpus(runtime, {"RESONANCE_PURGE_CORPUS": "1"})
            self.assertEqual(runtime.live.session_kinds(), {})
            # An index over nothing is still an index, and must not read stale.
            self.assertTrue(runtime.live.health().index_current)

            graph = ThoughtGraph.from_dict(minimal_thought("thought-first", "heat"))
            for mode in ("analogical", "structural"):
                result = runtime.live.discover(graph, mode=mode)
                self.assertEqual(result.get("matches_in_backend_order") or [], [])
                said = phrasing.say("resonance_discover", result)
                # Not "no results": the thought stays in the standing search,
                # and that is the whole answer a first arrival is owed.
                self.assertIn("stays in the search", said)
                self.assertNotIn("failure", said.lower())
        finally:
            runtime.live.repo.close()


class PurgeSessionsRetractsBothSidesTests(unittest.TestCase):
    def test_deleting_a_thought_removes_the_alert_recorded_for_the_other_person(self):
        # `retract_for_session` reaches only the owner's own side. The alert
        # recorded for the person on the other end still named the deleted
        # thought and survived until they next looked.
        runtime = _runtime()
        try:
            repo = runtime.live.repo
            ids = [s.session_id for s in repo.list_sessions()]
            mine, theirs = ids[0], ids[1]
            owner = repo.get_session(mine).user_id
            counterpart = repo.get_session(theirs).user_id
            my_key = _an_alert(runtime, owner, mine, theirs)
            their_key = _an_alert(runtime, counterpart, theirs, mine)

            result = product_server.startup_purge_sessions(
                runtime, {"RESONANCE_PURGE_SESSIONS": mine})
            self.assertEqual(result["deleted"], 1)
            self.assertEqual(result["alerts_retracted"], 2)
            self.assertIsNone(repo.get_grant(ALERT_KIND, my_key))
            self.assertIsNone(repo.get_grant(ALERT_KIND, their_key))
        finally:
            runtime.live.repo.close()


if __name__ == "__main__":
    unittest.main()
