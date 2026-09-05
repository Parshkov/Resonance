"""Whose reasoning is being shared (2026-09-05).

A conversation with an assistant is half the assistant's words, and the
assistant is the same one for everybody using this. If the structure that gets
indexed is one it wrote — its summary, its diagnosis, the framing it offered
that the person agreed with — then Resonance introduces people to an
assistant's habits rather than to each other. Worse, because those habits are
the same in every conversation it has, everyone would eventually match
everyone, and the signal the whole product depends on is that a thought belongs
to one person.

Nothing here can verify whose words they were: the conversation is never sent
to this service, by design, and both directories forbid pulling it. What it can
do is make the claim explicit, refuse the value that admits the assistant
supplied the shape, and hand the accepted claim back so the PERSON is shown it
and can say "no, that was your idea".
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.product.mcp_bridge import TOOLS, BridgeError, RemoteMCPBridge  # noqa: E402
from src.product.server import build_runtime  # noqa: E402

THOUGHT = {"topic": "pressure", "domain": "organisations",
           "nodes": [{"id": "n0", "label": "delivery pressure", "role": "problem"},
                     {"id": "n1", "label": "skipped review", "role": "mechanism"},
                     {"id": "n2", "label": "rework", "role": "outcome"}],
           "relations": [{"source": "n0", "target": "n1", "type": "causes"},
                         {"source": "n1", "target": "n2", "type": "causes"}]}


class AuthorshipTests(unittest.TestCase):
    def setUp(self):
        self.runtime = build_runtime(":memory:",
                                     allowed_origins=frozenset({"http://127.0.0.1"}),
                                     seed=False)
        self.bridge = RemoteMCPBridge(self.runtime.product)
        self.creds = self.runtime.product.register_guest()

    def _prepare(self, **extra):
        return self.bridge.tool_prepare_thought(
            self.creds.access_token, {"thought": THOUGHT, "request_id": "r1", **extra})

    def test_it_is_required(self):
        with self.assertRaises(BridgeError) as caught:
            self._prepare()
        self.assertIn("authorship", str(caught.exception))

    def test_a_shape_the_assistant_proposed_is_refused(self):
        with self.assertRaises(BridgeError) as caught:
            self._prepare(authorship="i_proposed_it")
        message = str(caught.exception)
        # The refusal has to say what to do instead, or the assistant will
        # simply pick a different value and carry on.
        self.assertIn("their own words", message)

    def test_an_unknown_claim_is_refused_rather_than_assumed_harmless(self):
        with self.assertRaises(BridgeError):
            self._prepare(authorship="probably_theirs")
        with self.assertRaises(BridgeError):
            self._prepare(authorship="")

    def test_the_persons_own_words_are_accepted(self):
        result = self._prepare(authorship="their_own_words")
        self.assertEqual(result["authorship"], "their_own_words")

    def test_reorganising_their_claims_is_accepted_and_said_so(self):
        result = self._prepare(authorship="their_words_reorganised")
        self.assertEqual(result["authorship"], "their_words_reorganised")
        self.assertIn("Nothing was added", result["authorship_note"])

    def test_the_claim_is_handed_back_for_the_person_to_check(self):
        """The person is the only one who can actually tell, so they must see
        the claim rather than have it made on their behalf in silence."""
        result = self._prepare(authorship="their_own_words")
        self.assertIn("did not write it", result["authorship_note"])
        self.assertIn("recognise the reasoning as their own", result["next_step"])
        self.assertIn("not whether it is correct", result["next_step"])

    def test_the_tool_declares_it_and_names_the_refused_value(self):
        tool = next(t for t in TOOLS if t["name"] == "resonance_prepare_thought")
        schema = tool["inputSchema"]
        self.assertIn("authorship", schema.get("required", []))
        self.assertEqual(schema["properties"]["authorship"]["enum"],
                         ["their_own_words", "their_words_reorganised", "i_proposed_it"])
        self.assertIn("REFUSED", schema["properties"]["authorship"]["description"])

    def test_the_description_gives_the_assistant_a_test_it_can_apply(self):
        tool = next(t for t in TOOLS if t["name"] == "resonance_prepare_thought")
        self.assertIn("could they have said this without you", tool["description"])

    def test_the_server_instructions_carry_the_rule_and_the_reason(self):
        reply = self.bridge.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18"}}, "")
        instructions = reply["result"]["instructions"]
        self.assertIn("half your words", instructions)
        self.assertIn("everyone to everyone", instructions)


if __name__ == "__main__":
    unittest.main()
