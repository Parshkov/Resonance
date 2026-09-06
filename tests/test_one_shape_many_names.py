"""One shape arriving from many unrelated accounts is not a resonance (2026-09-05).

`authorship.py` makes the assistant say whose reasoning it is sharing. Nothing
checked the answer. These tests pin the check that can be made without seeing
the conversation: when one exact label-free skeleton is held by a large share
of every account on the service, matches that rest on that skeleton alone are
set aside -- and, just as important, when it is not, nothing is touched.

Both directions are tested on purpose. A wrongly deleted match is invisible to
everyone, so the tests that prove real matches survive are the ones that
matter more.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.graph import ThoughtGraph  # noqa: E402
from src.product import shapes  # noqa: E402
from src.product.mcp_bridge import RemoteMCPBridge, build_thought_dna  # noqa: E402
from src.product.server import build_runtime  # noqa: E402


def thought(topic: str, nodes: list[tuple[str, str]],
            relations: list[tuple[int, int, str]]) -> dict:
    return {"topic": topic, "domain": "general",
            "nodes": [{"id": f"n{i}", "label": label, "role": role}
                      for i, (label, role) in enumerate(nodes)],
            "relations": [{"source": f"n{a}", "target": f"n{b}", "type": kind}
                          for a, b, kind in relations]}


# The shape ops/populate_local.py seeds three people with: four nodes, three
# relations, two relation types. Small, tidy, and exactly what an assistant's
# favourite framing looks like.
TIDY = [(0, 1, "causes"), (1, 2, "causes"), (3, 2, "prevents")]
TEAM = thought("pressure", [("pressure to ship", "problem"), ("skipped review", "mechanism"),
                            ("rework", "outcome"), ("jittered backoff", "method")], TIDY)
SOIL = thought("soil", [("over-fertilising", "problem"), ("salt accumulation", "mechanism"),
                        ("root damage", "outcome"), ("leaching schedule", "method")], TIDY)
CLINIC = thought("clinic", [("waiting-list pressure", "problem"), ("skipped triage", "mechanism"),
                            ("readmission", "outcome"), ("nurse callback", "method")], TIDY)

# A different shape for the clones, so the genuine pair above is never the
# thing being condemned: five nodes, four relations, three relation types.
HABIT = [(0, 1, "causes"), (1, 2, "causes"), (3, 1, "prevents"), (4, 3, "requires")]


def clone(i: int) -> dict:
    """The same skeleton in different words every time: what fifty assistants
    proposing one framing to fifty people would send."""
    words = [("load", "backlog", "delay", "throttle", "budget"),
             ("heat", "expansion", "cracking", "cooling", "power"),
             ("debt", "interest", "default", "repayment", "income"),
             ("rain", "runoff", "flooding", "drainage", "maintenance")][i % 4]
    return thought(f"clone-{i}",
                   [(f"{words[0]} {i}", "problem"), (f"{words[1]} {i}", "mechanism"),
                    (f"{words[2]} {i}", "outcome"), (f"{words[3]} {i}", "method"),
                    (f"{words[4]} {i}", "resource")], HABIT)


def dna_of(spec: dict) -> dict:
    """The same Thought DNA the bridge builds from a structured thought."""
    return build_thought_dna(spec, human_id="someone")


class SignatureTests(unittest.TestCase):
    """The signature is over the wiring, never the words."""

    def graph(self, spec: dict) -> ThoughtGraph:
        return ThoughtGraph.from_dict(dna_of(spec))

    def test_same_wiring_in_different_words_is_one_shape(self):
        self.assertEqual(shapes.shape_signature(self.graph(TEAM)),
                         shapes.shape_signature(self.graph(SOIL)))

    def test_node_ids_and_order_do_not_matter(self):
        reordered = dict(SOIL)
        reordered["nodes"] = [dict(n, id="x" + n["id"]) for n in reversed(SOIL["nodes"])]
        reordered["relations"] = [dict(r, source="x" + r["source"], target="x" + r["target"])
                                  for r in reversed(SOIL["relations"])]
        self.assertEqual(shapes.shape_signature(self.graph(SOIL)),
                         shapes.shape_signature(self.graph(reordered)))

    def test_different_wiring_is_a_different_shape(self):
        words = [(n["label"], n["role"]) for n in SOIL["nodes"]]
        flipped = thought("soil", words,
                          [(0, 1, "causes"), (1, 2, "causes"), (3, 2, "causes")])
        self.assertNotEqual(shapes.shape_signature(self.graph(SOIL)),
                            shapes.shape_signature(self.graph(flipped)))
        other_role = thought("soil", [(n["label"], "state" if i == 3 else n["role"])
                                      for i, n in enumerate(SOIL["nodes"])], TIDY)
        self.assertNotEqual(shapes.shape_signature(self.graph(SOIL)),
                            shapes.shape_signature(self.graph(other_role)))


class CensusVerdictTests(unittest.TestCase):
    """Each verdict, on a synthetic corpus, without touching the engine."""

    def dna(self, spec: dict) -> dict:
        return dna_of(spec)

    def test_verdicts(self):
        tidy = self.dna(SOIL)
        habit = self.dna(clone(0))
        tiny = self.dna(thought("tiny", [("a", "problem"), ("b", "outcome")],
                                [(0, 1, "causes")]))
        sig = shapes.shape_signature(ThoughtGraph.from_dict(tidy))
        habit_sig = shapes.shape_signature(ThoughtGraph.from_dict(habit))
        tiny_sig = shapes.shape_signature(ThoughtGraph.from_dict(tiny))

        # Three people on a tidy shape: the populate_local case. Coincidence.
        census = shapes.ShapeCensus.of([(f"u{i}", tidy) for i in range(3)])
        self.assertEqual(census.verdict(sig), shapes.COINCIDENCE)

        # Fifty accounts, one exact habit: a signature.
        census = shapes.ShapeCensus.of([(f"u{i}", habit) for i in range(50)])
        self.assertEqual(census.verdict(habit_sig), shapes.SIGNATURE)

        # The same fifty inside a corpus of five hundred: a popular idea, and
        # a popular idea is not a defect.
        rows = [(f"u{i}", habit) for i in range(50)]
        rows += [(f"v{i}", tidy) for i in range(450)]
        census = shapes.ShapeCensus.of(rows)
        self.assertEqual(census.verdict(habit_sig), shapes.POPULAR)
        self.assertEqual(census.verdict(sig), shapes.SIGNATURE)

        # A one-relation chain held by everyone is what short inputs become;
        # it is never judged.
        census = shapes.ShapeCensus.of([(f"u{i}", tiny) for i in range(50)])
        self.assertEqual(census.verdict(tiny_sig), shapes.TOO_SMALL)

        # One account with fifty thoughts of one shape is one person, not fifty.
        census = shapes.ShapeCensus.of([("u0", habit) for _ in range(50)])
        self.assertEqual(census.verdict(habit_sig), shapes.COINCIDENCE)

        # An empty census condemns nothing.
        self.assertEqual(shapes.ShapeCensus.of([]).verdict(habit_sig), shapes.COINCIDENCE)

    def test_summary_names_nobody(self):
        habit = self.dna(clone(0))
        census = shapes.ShapeCensus.of([(f"u{i}", habit) for i in range(13)]
                                       + [("lonely", self.dna(SOIL))])
        summary = census.summary(minimum=3)
        text = str(summary)
        for count in census.counts.values():
            self.assertNotIn(count.signature, text)
        self.assertNotIn("lonely", text)
        self.assertEqual(summary["shapes_held_by_fewer_than_minimum"], 1)
        self.assertEqual(summary["shapes"][0]["verdict"], shapes.SIGNATURE)
        self.assertEqual(summary["shapes"][0]["share_of_accounts"], 0.93)


class DiscoveryTests(unittest.TestCase):
    """The rule where it acts: a row is dropped from discovery, or it is not."""

    def setUp(self):
        self.runtime = build_runtime(":ephemeral:",
                                     allowed_origins=frozenset({"http://127.0.0.1"}),
                                     seed=False)
        self.product = self.runtime.product
        self.bridge = RemoteMCPBridge(self.product)

    def share(self, what: dict, tag: str):
        who = self.product.register_guest()
        token = who.access_token
        draft = self.bridge.tool_prepare_thought(
            token, {"authorship": "their_own_words", "thought": what,
                    "request_id": tag + "-1"})
        receipt = self.bridge.tool_share_thought(
            token, {"draft_id": draft["draft_id"], "confirm": True,
                    "confirmation_token": draft["confirmation_token"],
                    "request_id": tag + "-2"})
        return who, receipt["session_id"]

    def discover(self, who, session_id) -> dict:
        result = self.bridge.tool_discover(who.access_token, {"session_id": session_id})
        return result.result if hasattr(result, "result") else result

    def owners(self, rows) -> set[str]:
        source = self.product.identity.policy_source
        return {source.owner_of("session", row["session_id"]) for row in rows}

    def test_one_shape_from_many_accounts_is_set_aside(self):
        clones = [self.share(clone(i), f"clone{i}") for i in range(shapes.MIN_ACCOUNTS + 2)]
        first, first_session = clones[0]
        before = self.product.live.discover(
            ThoughtGraph.from_dict(dict(self.product.backend.get_session(first_session).thought_dna)),
            mode="analogical", k=8)
        # The engine itself does find them: the shapes are identical, so this
        # is precisely the case nothing below the product boundary can catch.
        self.assertGreater(len(before["matches"]) + len(before["rejected"]), 0)

        seen = self.discover(first, first_session)
        self.assertEqual(seen["matches_in_backend_order"], [])
        self.assertEqual(seen["rejected"], [])
        self.assertEqual(seen["shape_note"], shapes.SAME_SHAPE_NOTE)

    def test_a_genuine_match_beside_the_habit_survives(self):
        for i in range(shapes.MIN_ACCOUNTS + 2):
            self.share(clone(i), f"clone{i}")
        mine, my_session = self.share(TEAM, "mine")
        theirs, _ = self.share(SOIL, "theirs")
        seen = self.discover(mine, my_session)
        found = [row for row in seen["matches_in_backend_order"]
                 if not row.get("hard_rejection")]
        self.assertIn(theirs.user_id, self.owners(found))
        self.assertEqual(seen["shape_note"], "")

    def test_a_small_corpus_is_never_judged(self):
        """The populate_local case: three people, one shape, all genuine. Any
        rule that fires here deletes the product's own demonstration."""
        bea, bea_session = self.share(SOIL, "bea")
        cai, _ = self.share(CLINIC, "cai")
        dov, _ = self.share(TEAM, "dov")
        seen = self.discover(bea, bea_session)
        self.assertEqual(self.owners(seen["matches_in_backend_order"]),
                         {cai.user_id, dov.user_id})
        self.assertEqual(seen["shape_note"], "")
        census = self.product.shape_census()
        self.assertEqual(census["shapes"][0]["verdict"], shapes.COINCIDENCE)
        self.assertEqual(census["shapes"][0]["held_by_accounts"], 3)

    def test_the_person_is_told_about_the_shape_and_nothing_else(self):
        clones = [self.share(clone(i), f"clone{i}") for i in range(shapes.MIN_ACCOUNTS)]
        first, first_session = clones[0]
        seen = self.discover(first, first_session)
        note = seen["shape_note"]
        self.assertTrue(note)
        self.assertNotIn(str(shapes.MIN_ACCOUNTS), note)
        for who, session in clones[1:]:
            self.assertNotIn(who.user_id, note)
            self.assertNotIn(session, note)
        self.assertNotIn("blame", note.lower())
        self.assertIn("not about you", note)

    def test_a_stored_result_is_re_filtered_on_read(self):
        """The census can move between a discovery and a later read of it. A
        re-read may only shrink, the same way blocks and consent already work."""
        mine, my_session = self.share(clone(0), "mine")
        others = [self.share(clone(i), f"clone{i}") for i in range(1, shapes.MIN_ACCOUNTS - 2)]
        seen = self.discover(mine, my_session)
        self.assertGreater(len(seen["matches_in_backend_order"]), 0)
        for i in range(shapes.MIN_ACCOUNTS - 2, shapes.MIN_ACCOUNTS + 1):
            self.share(clone(i), f"late{i}")
        # The corpus generation moved, so the stored result is stale by the
        # existing rule; a fresh discovery is what the person would run next.
        again = self.discover(mine, my_session)
        self.assertEqual(again["matches_in_backend_order"], [])
        self.assertEqual(again["shape_note"], shapes.SAME_SHAPE_NOTE)
        self.assertGreater(len(others), 0)


if __name__ == "__main__":
    unittest.main()
