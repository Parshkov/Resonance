"""Every verdict the engine can reach must be sayable to a person (2026-09-05).

Asked by Parshkov while testing on a real conversation about software radio:
"we need like-minded people, and not necessarily from another field. What if
they also do radio and think very closely -- does our system show them or push
them away?"

It shows them. `classify` sends same-subject pairs down `_direct_or_approximate`
and they are not filtered anywhere. But it had no words for them. The table in
the chat and the table on the page both carried a phrase for "literal", which
the engine has never returned, and none for "direct" or "complementary", which
it does -- so someone matched inside their own field was told they were a
"direct", and the pair where each holds exactly what the other lacks was told
"complementary".

The only verdict with human words was "analogical" -- "same shape, different
subject". That is why the product read as if it wanted people from another
field and nobody else, when the engine had never said any such thing.

So the list lives in the engine, and both tables are checked against it here
rather than against a hand-written copy of it.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import src.alignment  # noqa: F401,E402  (import order: breaks a circular import)
from src.scoring import CLASSIFICATIONS  # noqa: E402
from src.product.phrasing import CLASSIFICATION_IN_WORDS, classification  # noqa: E402

PAGE = (REPO / "demo" / "ui" / "app.mjs").read_text(encoding="utf-8")


class EveryVerdictHasWordsTests(unittest.TestCase):
    def test_the_chat_can_say_all_of_them(self):
        for verdict in CLASSIFICATIONS:
            with self.subTest(verdict):
                said = classification(verdict)
                self.assertNotEqual(said, verdict,
                                    f"{verdict!r} reaches a person as the engine's own word")
                self.assertIn(" ", said, f"{verdict!r} is not a phrase a person would say")

    def test_the_page_can_say_all_of_them(self):
        block = PAGE[PAGE.index("const CLASSIFICATION_IN_WORDS"):]
        block = block[:block.index("};")]
        for verdict in CLASSIFICATIONS:
            with self.subTest(verdict):
                self.assertIn(f"{verdict}:", block,
                              f"the page has no words for {verdict!r}")

    def test_same_subject_is_not_described_as_a_lesser_match(self):
        """Someone already working on your problem is the plainest reason to
        meet, and the words must not read as a consolation for failing to be
        an analogy."""
        said = classification("direct")
        self.assertNotIn("not", said)
        self.assertNotIn("close", said)

    def test_the_two_tables_agree(self):
        for verdict, words in CLASSIFICATION_IN_WORDS.items():
            with self.subTest(verdict):
                self.assertIn(words, PAGE,
                              f"the page says something different for {verdict!r}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
