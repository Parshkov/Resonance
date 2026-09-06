"""The shared topic (2026-09-05).

Two people introduced here never talk to each other directly: each talks to
their own assistant, and the assistants meet in Resonance. Relaying prose
through two language models would waste what an assistant is for — explaining a
stranger's idea in its own person's terms — and the meaning drifts a little on
every hop.

So what accumulates is structure, not a transcript, and every read is a delta.
These tests hold that: what one side contributes reaches the other once, the
engine that introduced them is the same one that says where they now agree and
disagree, and nobody outside the workspace can read or write any of it.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.product.mcp_bridge import RemoteMCPBridge  # noqa: E402
from src.product.server import build_runtime  # noqa: E402
from src.workspaces.service import WorkspaceError  # noqa: E402
from src.workspaces.topics import SharedTopicService, TopicError  # noqa: E402

PUSHED = {"topic": "pressure", "domain": "organisations",
          "nodes": [{"id": "n0", "label": "delivery pressure", "role": "problem"},
                    {"id": "n1", "label": "skipped review", "role": "mechanism"},
                    {"id": "n2", "label": "rework", "role": "outcome"}],
          "relations": [{"source": "n0", "target": "n1", "type": "causes"},
                        {"source": "n1", "target": "n2", "type": "causes"}]}
FED = {"topic": "soil", "domain": "agriculture",
       "nodes": [{"id": "m0", "label": "yield pressure", "role": "problem"},
                 {"id": "m1", "label": "salt accumulation", "role": "mechanism"},
                 {"id": "m2", "label": "root damage", "role": "outcome"}],
       "relations": [{"source": "m0", "target": "m1", "type": "causes"},
                     {"source": "m1", "target": "m2", "type": "causes"}]}


class TopicTests(unittest.TestCase):
    def setUp(self):
        self.runtime = build_runtime(":ephemeral:",
                                     allowed_origins=frozenset({"http://127.0.0.1"}),
                                     seed=False)
        self.bridge = RemoteMCPBridge(self.runtime.product)
        self.workspaces = self.runtime.product.workspaces
        self.topics = SharedTopicService(self.workspaces)
        self.alice, alice_session = self._share("alice", PUSHED)
        self.bob, bob_session = self._share("bob", FED)
        self.bridge.tool_request_intro(self.alice.access_token, {
            "from_session_id": alice_session, "target_session_id": bob_session,
            "message": "Different field, same shape?", "confirm": True,
            "request_id": "i1"})
        incoming = self.bridge.tool_list_intros(self.bob.access_token, {})["incoming"]
        accepted = self.bridge.tool_respond_intro(self.bob.access_token, {
            "intro_id": incoming[0]["intro_id"], "accept": True, "confirm": True,
            "request_id": "i2"})
        self.workspace = self.workspaces.create_from_intro(
            self.alice.access_token, accepted["intro_id"],
            title="Pressure that backfires")["workspace_id"]
        self.workspaces.respond_invite(self.bob.access_token, self.workspace,
                                       accept=True)

    def _share(self, tag, thought):
        creds = self.runtime.product.register_guest()
        prepared = self.bridge.tool_prepare_thought(
            creds.access_token, {"authorship": "their_own_words", "thought": thought, "request_id": f"{tag}-1"})
        self.bridge.tool_share_thought(creds.access_token, {
            "confirm": True, "request_id": f"{tag}-2",
            "draft_id": prepared["draft_id"],
            "confirmation_token": prepared["confirmation_token"]})
        return creds, prepared["session_id"]

    def _contribute(self, who, thought, note):
        return self.topics.contribute(who.access_token, self.workspace,
                                      thought=thought, note=note, confirmed=True)

    # -- the mechanic ---------------------------------------------------
    def test_what_one_side_contributes_reaches_the_other(self):
        self._contribute(self.alice, PUSHED, "Slack time is what actually prevents it.")
        seen = self.topics.read(self.bob.access_token, self.workspace)
        self.assertEqual(seen["new_for_you"], 1)
        self.assertEqual(seen["delta"][0]["note"],
                         "Slack time is what actually prevents it.")
        self.assertTrue(seen["delta"][0]["untrusted"],
                        "another person's words must be marked as theirs")

    def test_a_reader_is_shown_each_contribution_once(self):
        """Every read is a delta. Replaying the history would spend the
        assistant's context on the archive instead of on the new thing."""
        self._contribute(self.alice, PUSHED, "first")
        self.assertEqual(self.topics.read(self.bob.access_token, self.workspace)["new_for_you"], 1)
        self.assertEqual(self.topics.read(self.bob.access_token, self.workspace)["new_for_you"], 0)
        self._contribute(self.alice, PUSHED, "second")
        self.assertEqual(self.topics.read(self.bob.access_token, self.workspace)["new_for_you"], 1)

    def test_your_own_contribution_is_never_news_to_you(self):
        self._contribute(self.bob, FED, "mine")
        self.assertEqual(self.topics.read(self.bob.access_token, self.workspace)["new_for_you"], 0)

    def test_a_glance_can_leave_the_cursor_where_it_was(self):
        self._contribute(self.alice, PUSHED, "first")
        glanced = self.topics.read(self.bob.access_token, self.workspace, advance=False)
        self.assertEqual(glanced["new_for_you"], 1)
        self.assertEqual(self.topics.read(self.bob.access_token, self.workspace)["new_for_you"], 1)

    def test_the_topic_says_where_the_two_sides_agree(self):
        """Computed by the same engine that introduced them, so what the topic
        says cannot drift away from the match it grew out of."""
        self._contribute(self.alice, PUSHED, "mine")
        self._contribute(self.bob, FED, "theirs")
        standing = self.topics.read(self.alice.access_token, self.workspace)["standing"]
        self.assertTrue(standing["available"])
        side = standing["sides"][0]
        self.assertGreater(len(side["agreed_nodes"]), 0)
        self.assertGreater(side["agreed_relations"], 0)
        self.assertIn("contested", side)
        self.assertIn("classification", side)

    def test_it_says_what_is_missing_before_you_have_said_anything(self):
        self._contribute(self.bob, FED, "theirs")
        standing = self.topics.read(self.alice.access_token, self.workspace)["standing"]
        self.assertFalse(standing["available"])
        self.assertIn("contribute your own", standing["reason"])

    def test_the_shared_topic_is_structure_and_notes_only(self):
        result = self._contribute(self.alice, PUSHED, "a note")
        self.assertEqual(result["nodes"], 3)
        self.assertEqual(result["relations"], 2)
        delta = self.topics.read(self.bob.access_token, self.workspace)["delta"][0]
        self.assertIn("nodes", delta["thought"])
        self.assertIn("relations", delta["thought"])
        # Projected field by field: no source text, and no provenance block
        # naming the account it was built for.
        self.assertNotIn("source", delta["thought"])
        self.assertNotIn("provenance", delta["thought"])

    # -- consent and boundaries -----------------------------------------
    def test_contributing_needs_the_person_s_explicit_approval(self):
        with self.assertRaises(TopicError):
            self.topics.contribute(self.alice.access_token, self.workspace,
                                   thought=PUSHED, note="", confirmed=False)

    def test_a_stranger_can_neither_read_nor_contribute(self):
        stranger = self.runtime.product.register_guest()
        with self.assertRaises(WorkspaceError):
            self.topics.read(stranger.access_token, self.workspace)
        with self.assertRaises(WorkspaceError):
            self.topics.contribute(stranger.access_token, self.workspace,
                                   thought=PUSHED, note="", confirmed=True)

    def test_a_contribution_must_actually_carry_reasoning(self):
        for bad in ({}, {"nodes": [], "relations": []},
                    {"nodes": [{"id": "a", "label": "one", "role": "problem"}],
                     "relations": []}, "not a graph", None):
            with self.assertRaises(TopicError, msg=repr(bad)):
                self.topics.contribute(self.alice.access_token, self.workspace,
                                       thought=bad, note="", confirmed=True)

    def test_a_note_has_a_bound(self):
        with self.assertRaises(TopicError):
            self.topics.contribute(self.alice.access_token, self.workspace,
                                   thought=PUSHED, note="x" * 1001, confirmed=True)

    def test_a_pseudonym_is_all_anyone_learns_about_the_author(self):
        self._contribute(self.alice, PUSHED, "mine")
        delta = self.topics.read(self.bob.access_token, self.workspace)["delta"][0]
        self.assertNotIn(self.alice.user_id, str(delta))
        self.assertTrue(delta["author_pseudonym"])

    def test_more_than_two_people_can_hold_one_topic(self):
        """The point of a topic rather than a channel: a group can form around
        one shape, not just a pair."""
        third, third_session = self._share("carol", PUSHED)
        self.bridge.tool_request_intro(self.alice.access_token, {
            "from_session_id": self._alice_session(), "target_session_id": third_session,
            "message": "join us?", "confirm": True, "request_id": "i3"})
        incoming = self.bridge.tool_list_intros(third.access_token, {})["incoming"]
        self.bridge.tool_respond_intro(third.access_token, {
            "intro_id": incoming[0]["intro_id"], "accept": True, "confirm": True,
            "request_id": "i4"})
        self.workspaces.invite(self.alice.access_token, self.workspace, third.user_id)
        self.workspaces.respond_invite(third.access_token, self.workspace, accept=True)

        self._contribute(self.alice, PUSHED, "from alice")
        self._contribute(self.bob, FED, "from bob")
        seen = self.topics.read(third.access_token, self.workspace)
        self.assertEqual(seen["new_for_you"], 2)
        authors = {row["author_pseudonym"] for row in seen["delta"]}
        self.assertEqual(len(authors), 2)

    def _alice_session(self):
        owned = self.runtime.product.owned_sessions(self.alice.access_token)
        return owned[0]["session_id"]


if __name__ == "__main__":
    unittest.main()


class OneIndexOneLanguageTests(unittest.TestCase):
    """Matching compares meaning as well as shape, and meaning is compared
    through an English lexicon. Structure crosses languages perfectly; meaning
    does not, and meaning is what decides whether a structural match is
    reported as a match at all. Measured, not assumed:

        english <-> english, different words   structural 0.7071  semantic 0.3923  analogical
        english <-> russian, same thought      structural 0.7071  semantic 0.0000  NEGATIVE
        russian <-> russian, different words   structural 0.7071  semantic 0.1111  NEGATIVE

    So two people holding the same thought in different languages would never
    be introduced, and two Russian speakers would meet only by using identical
    wording. Until the semantics are multilingual, the assistant carries the
    translation: it labels in English and speaks to its person in their own
    language. These tests pin that instruction, because losing it silently
    would make the product quietly find nobody outside English.
    """

    def test_the_thought_schema_states_that_labels_are_matched_as_english(self):
        """The schema states the fact; `instructions` carries the instruction.

        This used to shout "WRITE THE LABELS IN ENGLISH ... that is your job
        here, not theirs" from inside the tool schema. It is a true and
        necessary requirement, and it was in the wrong place: a schema
        description is data from a third-party server, and one written as an
        order to the model is what a prompt-injection payload looks like.
        ChatGPT's safety layer flagged this surface and then blocked the share
        call, which took the product's central action away in that client.

        The requirement did not move far. The schema says what the server
        does -- labels are matched as English text, so another language
        matches nothing -- and the next test holds the instruction itself in
        `instructions`, which is the field MCP defines for telling an
        assistant how to use a server.
        """
        from src.product.mcp_bridge import THOUGHT_SCHEMA
        description = THOUGHT_SCHEMA["description"]
        self.assertIn("English", description)
        self.assertIn("another language", description)
        self.assertNotIn("ENGLISH", description)

    def test_the_server_instructions_say_it_too_and_say_why(self):
        from src.product.mcp_bridge import RemoteMCPBridge
        from src.product.server import build_runtime
        runtime = build_runtime(":ephemeral:",
                                allowed_origins=frozenset({"http://127.0.0.1"}),
                                seed=False)
        bridge = RemoteMCPBridge(runtime.product)
        reply = bridge.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                               "params": {"protocolVersion": "2025-06-18"}}, "")
        instructions = reply["result"]["instructions"]
        self.assertIn("English", instructions)
        self.assertIn("their own language", instructions)
        self.assertIn("different languages should still meet", instructions)
