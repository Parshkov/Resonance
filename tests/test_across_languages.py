"""The same reasoning, said in two languages (2026-09-05).

The product's claim is that it matches on the shape of an argument, not on
the words carrying it. That claim is worth exactly as much as its evidence,
and until now the evidence was a number printed once during development. If
the Russian lexicon regressed, or the stemmer started reducing words into
each other, the product would keep introducing people and simply be wrong
about why.

So this holds the claim directly: the same causal chain written in English
and in Russian must be recognised as the same reasoning, and a Russian
chain that argues something else must not be.
"""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.engine.facade import ResonanceEngine  # noqa: E402
from src.graph import ThoughtGraph  # noqa: E402


def graph(topic: str, labels: tuple[str, str, str]) -> ThoughtGraph:
    problem, mechanism, outcome = labels
    text = " -> ".join(labels)
    return ThoughtGraph.from_dict({
        "schema_version": "thought-dna/0.1", "thought_id": topic,
        "provenance": {"kind": "manual", "human_id": "test", "extractor": None},
        "source": {"text": text,
                   "sha256": hashlib.sha256(text.encode()).hexdigest()},
        "nodes": [
            {"id": "n0", "label": problem, "role": "state", "spans": [],
             "extract_conf": 1.0, "atomic": True},
            {"id": "n1", "label": mechanism, "role": "mechanism", "spans": [],
             "extract_conf": 1.0, "atomic": True},
            {"id": "n2", "label": outcome, "role": "outcome", "spans": [],
             "extract_conf": 1.0, "atomic": True},
        ],
        "relations": [
            {"id": "r0", "source": "n0", "target": "n1", "type": "causes",
             "extract_conf": 1.0, "spans": []},
            {"id": "r1", "source": "n1", "target": "n2", "type": "causes",
             "extract_conf": 1.0, "spans": []},
        ]})


# One argument: pressure to ship makes people skip review, which produces rework.
ENGLISH = graph("delivery", ("delivery pressure", "skipped review", "rework"))
RUSSIAN = graph("поставка", ("давление сроков", "пропущенная проверка", "переделка"))
# A different argument in the same language, to prove the match is not just
# "both are Russian" or "both have three nodes".
UNRELATED = graph("почва", ("нехватка воды", "накопление соли", "гибель корней"))


class AcrossLanguagesTests(unittest.TestCase):
    def setUp(self):
        self.engine = ResonanceEngine()

    def _compare(self, a, b):
        return self.engine.compare(a, b, mode="analogical")

    def test_the_same_argument_in_two_languages_is_one_argument(self):
        verdict = self._compare(ENGLISH, RUSSIAN)
        self.assertEqual(verdict.classification, "analogical", verdict.classification)
        self.assertGreater(verdict.components.semantic, 0.5,
                           f"semantic={verdict.components.semantic}")
        self.assertEqual(len(verdict.matched_relations), 2, verdict.matched_relations)

    def test_it_is_the_meaning_that_carries_across_and_not_the_alphabet(self):
        """Two Russian chains that argue different things stay different.

        Without this, a lexicon that mapped every unknown Cyrillic word onto
        one fallback class would pass the test above and mean nothing.
        """
        same = self._compare(ENGLISH, RUSSIAN).components.semantic
        other = self._compare(RUSSIAN, UNRELATED).components.semantic
        self.assertGreater(same, other, f"same={same} other={other}")

    def test_russian_words_resolve_to_concepts_at_all(self):
        """The failure this guards is silent: an empty lexicon still returns a
        structural match, so a comparison can look healthy while no Russian
        word was understood."""
        from src.semantics.similarity import abstract_concepts

        for word, expected in (("давление", True), ("проверка", True),
                               ("накопление", True), ("да", False)):
            self.assertEqual(bool(abstract_concepts(word)), expected,
                             f"{word} -> {sorted(abstract_concepts(word))}")


if __name__ == "__main__":
    unittest.main()
