"""What a tool result sounds like to a person (2026-09-05).

Every tool answered with json.dumps(result) as its one text block. MCP clients
show that block, so someone asking their assistant "am I sharing anything?"
was shown contract_version, session ids and a score vector — in a service
whose entire purpose is a conversation between people. Parshkov put it
plainly: the answer looked like JSON when it should have looked human.

These hold the fix without letting it become a second, looser source of
truth: the structured half stays byte-for-byte what it was, the sentence
never claims something the data does not say, and a tool added later cannot
quietly go back to speaking JSON.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.product.mcp_bridge import TOOL_NAMES, RemoteMCPBridge  # noqa: E402
from src.product.phrasing import PHRASINGS, say  # noqa: E402
from src.product.server import build_runtime  # noqa: E402

MINE = {"topic": "pressure", "domain": "organisations",
        "nodes": [{"id": "n0", "label": "delivery pressure", "role": "problem"},
                  {"id": "n1", "label": "skipped review", "role": "mechanism"},
                  {"id": "n2", "label": "rework", "role": "outcome"}],
        "relations": [{"source": "n0", "target": "n1", "type": "causes"},
                      {"source": "n1", "target": "n2", "type": "causes"}]}
THEIRS = {"topic": "soil", "domain": "agriculture",
          "nodes": [{"id": "m0", "label": "yield pressure", "role": "problem"},
                    {"id": "m1", "label": "salt accumulation", "role": "mechanism"},
                    {"id": "m2", "label": "root damage", "role": "outcome"}],
          "relations": [{"source": "m0", "target": "m1", "type": "causes"},
                        {"source": "m1", "target": "m2", "type": "causes"}]}


class SpeaksHumanTests(unittest.TestCase):
    def setUp(self):
        self.runtime = build_runtime(":memory:",
                                     allowed_origins=frozenset({"http://127.0.0.1"}),
                                     seed=False)
        self.bridge = RemoteMCPBridge(self.runtime.product)
        self.mine = self.runtime.product.register_guest().access_token
        self.theirs = self.runtime.product.register_guest().access_token
        self._id = 0

    def call(self, token, name, arguments=None):
        self._id += 1
        response = self.bridge.handle(
            {"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
             "params": {"name": name, "arguments": arguments or {}}}, token)
        return response["result"]

    def share(self, token, thought, tag):
        draft = self.bridge.tool_prepare_thought(
            token, {"authorship": "their_own_words", "thought": thought,
                    "request_id": tag + "-1"})
        self.bridge.tool_share_thought(
            token, {"draft_id": draft["draft_id"], "confirm": True,
                    "confirmation_token": draft["confirmation_token"],
                    "request_id": tag + "-2"})

    def test_every_published_tool_has_something_to_say(self):
        self.assertEqual(sorted(set(TOOL_NAMES) - set(PHRASINGS)), [])

    def test_no_answer_is_handed_over_as_json(self):
        self.share(self.mine, MINE, "mine")
        self.share(self.theirs, THEIRS, "theirs")
        for token, name, arguments in (
            (self.mine, "resonance_whoami", {}),
            (self.mine, "resonance_my_thoughts", {}),
            (self.mine, "resonance_discover", {}),
            (self.mine, "resonance_list_intros", {}),
            (self.mine, "resonance_topics", {}),
            (self.theirs, "resonance_pending_resonances", {}),
        ):
            with self.subTest(name):
                text = self.call(token, name, arguments)["content"][0]["text"]
                self.assertFalse(text.lstrip().startswith(("{", "[")), text)
                self.assertNotIn("contract_version", text)
                self.assertNotIn("ses-", text)
                self.assertNotIn("person-", text)

    def test_a_refusal_is_the_sentence_it_was_written_as(self):
        """The refusals were written for a person to hear. Wrapping one in JSON
        only got the wrapper read out loud."""
        result = self.call(self.mine, "resonance_prepare_thought",
                           {"context": "some words"})
        self.assertTrue(result["isError"])
        text = result["content"][0]["text"]
        self.assertFalse(text.lstrip().startswith("{"), text)
        self.assertIn("authorship", text)
        # The machine half still carries the code a client may branch on.
        self.assertEqual(result["structuredContent"]["error"], "validation_failed")

    def test_the_structured_half_is_untouched(self):
        """The sentence is an addition. Anything that reads the data must see
        exactly what it saw before."""
        self.share(self.mine, MINE, "mine")
        result = self.call(self.mine, "resonance_whoami", {})
        direct = self.bridge.tool_whoami(self.mine, {})
        self.assertEqual(json.loads(json.dumps(result["structuredContent"], default=str)),
                         json.loads(json.dumps(direct, default=str)))

    def test_it_never_announces_a_person_the_engine_rejected(self):
        """The sentence must not be a second, looser judgement. A row the
        engine classifies negative is not a resonance, however tempting it is
        to say somebody turned up."""
        rejected = {"matches_in_backend_order": [
            {"person_pseudonym": "Nobody At All", "mode_classification": "negative"},
            {"person_pseudonym": "Also Nobody", "hard_rejection": "unsound"}]}
        text = say("resonance_discover", rejected)
        self.assertNotIn("Nobody At All", text)
        self.assertNotIn("Also Nobody", text)
        self.assertIn("not enough meaning", text)

    def test_nothing_found_is_said_as_an_answer_not_a_failure(self):
        text = say("resonance_discover", {"matches_in_backend_order": []})
        self.assertNotIn("error", text.lower())
        self.assertIn("arrives later", text)

    def test_a_clumsy_sentence_never_costs_the_answer(self):
        """If a phrasing ever raises, the result still has to reach the caller."""
        broken = {"shared_thoughts": "not a list, so len() will not do what it expects"}
        text = say("resonance_whoami", {**broken, "display_label": None})
        self.assertTrue(text)



class WithdrawnIsNotPrivateTests(unittest.TestCase):
    """A thought you took back is not "kept private here".

    Everything that was not discoverable fell into one bucket, so someone who
    had withdrawn their only thought was told by their assistant that one was
    still held here — while the page, correctly, showed nothing of theirs at
    all. Two answers to "what do I have here?", and the reassuring one was the
    wrong one.
    """

    def setUp(self):
        self.runtime = build_runtime(":memory:",
                                     allowed_origins=frozenset({"http://127.0.0.1"}),
                                     seed=False)
        self.bridge = RemoteMCPBridge(self.runtime.product)
        self.token = self.runtime.product.register_guest().access_token

    def test_a_withdrawn_thought_is_reported_as_withdrawn(self):
        draft = self.bridge.tool_prepare_thought(
            self.token, {"authorship": "their_own_words", "thought": MINE,
                         "request_id": "w-1"})
        shared = self.bridge.tool_share_thought(
            self.token, {"draft_id": draft["draft_id"], "confirm": True,
                         "confirmation_token": draft["confirmation_token"],
                         "request_id": "w-2"})
        before = self.bridge.tool_whoami(self.token, {})
        self.assertEqual(len(before["shared_thoughts"]), 1)

        self.bridge.tool_stop_sharing(
            self.token, {"session_id": shared["session_id"], "confirm": True})
        after = self.bridge.tool_whoami(self.token, {})
        self.assertEqual(after["shared_thoughts"], [])
        self.assertEqual(after["private_thoughts"], [],
                         "a withdrawn thought must not be called private")
        self.assertEqual(len(after["withdrawn_thoughts"]), 1)

        said = say("resonance_whoami", after)
        self.assertIn("withdrawn", said)
        self.assertNotIn("kept private", said)

if __name__ == "__main__":
    unittest.main()


class TextOnlyClientTests(unittest.TestCase):
    """A client that reads only the content blocks must still be able to act.

    Claude reads content blocks and not `structuredContent`. With the answer
    in words and nothing else, it said so itself: the server "didn't echo the
    exact node labels or a draft ID / confirmation token back to me, so I
    can't show you the literal label text it stored or proceed to sharing".

    Two things were broken by that, and only one of them is an integration
    detail. The person could not see the labels they were being asked to
    approve -- which is the consent promise, not a convenience -- and after
    approving, nothing could be shared, introduced or withdrawn.

    So the reply carries two text blocks. The first is for the person and
    holds no identifier; the second is the same result serialized, for the
    client. The tests above pin the first; this pins the second.
    """

    def setUp(self):
        self.runtime = build_runtime(":memory:",
                                     allowed_origins=frozenset({"http://127.0.0.1"}),
                                     seed=False)
        self.bridge = RemoteMCPBridge(self.runtime.product)

    def _call(self, token, name, arguments=None):
        return self.bridge.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": name, "arguments": arguments or {}}}, token)["result"]

    def test_a_thought_can_be_shared_reading_only_the_text_blocks(self):
        creds = self.runtime.product.register_guest()
        prepared = self._call(creds.access_token, "resonance_prepare_thought", {
            "authorship": "their_own_words",
            "context": ("Deadline pressure causes the code review to be rushed. "
                        "A rushed review causes the same defects to be fixed again. "
                        "Repeat fixes prevent the release being shipped on time."),
            "topic": "Deadline pressure repeats the fixes",
            "domain": "software-delivery"})

        spoken = prepared["content"][0]["text"]
        # The person sees what they are approving, in words, with no engine ids.
        self.assertIn("would become visible", spoken)
        self.assertIn("Deadline pressure", spoken)
        self.assertNotIn("draft-", spoken)

        # And the client can find what the next call needs, without ever
        # looking at structuredContent.
        machine = json.loads(prepared["content"][-1]["text"])
        shared = self._call(creds.access_token, "resonance_share_thought", {
            "draft_id": machine["draft_id"],
            "confirmation_token": machine["confirmation_token"],
            "confirm": True, "request_id": "text-only-1"})
        self.assertFalse(shared["isError"])
        self.assertTrue(json.loads(shared["content"][-1]["text"])["discoverable"])

    def test_every_answer_carries_the_serialized_result_last(self):
        creds = self.runtime.product.register_guest()
        for name in ("resonance_whoami", "resonance_my_thoughts",
                     "resonance_list_intros", "resonance_topics"):
            with self.subTest(name):
                blocks = self._call(creds.access_token, name)["content"]
                self.assertEqual(blocks[0]["type"], "text")
                self.assertFalse(blocks[0]["text"].lstrip().startswith(("{", "[")),
                                 "the first block is for a person")
                self.assertIsInstance(json.loads(blocks[-1]["text"]), dict)
