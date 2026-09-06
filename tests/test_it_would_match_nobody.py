"""A thought that could never match anyone must not be called discoverable.

Found on Parshkov's own conversation, in Russian, about software radio. The
server took Cyrillic node labels without a word, reported the thought as
shared and discoverable, and started a standing search for it. That search can
never return anything: the semantic layer compares labels as English text, and
`test_shared_topics` has the measurement -- English against Russian scores
0.0000, Russian against Russian in different words 0.1111, both NEGATIVE.

So the person was told the product was working for them while it was not, and
nothing anywhere would ever have said otherwise. That is the worst shape a
defect can take here, because the promise the product makes is precisely that
it keeps looking after you leave.

Refusing is not the ideal answer -- the ideal answer is a multilingual
semantic layer, and that is a real piece of work. Refusing is the honest one:
it tells the caller exactly what is wrong and exactly what to do, and an
assistant can translate labels in a single step while going on speaking to the
person in their own language.

`topic` and `domain` are shown to people and never matched, so they stay in
whatever language they were written in.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import src.alignment  # noqa: F401,E402  (import order: breaks a circular import)
from src.product.mcp_bridge import RemoteMCPBridge, BridgeError  # noqa: E402
from src.product.server import build_runtime  # noqa: E402

RUSSIAN = {
    "topic": "AI создаёт форму антенны",
    "domain": "adaptive-radio",
    "nodes": [{"label": "меняющиеся условия радиоэфира", "role": "problem"},
              {"label": "адаптивная топология", "role": "method"}],
    "relations": [{"source": "меняющиеся условия радиоэфира",
                   "target": "адаптивная топология", "type": "requires"}],
}
ENGLISH_LABELS_RUSSIAN_TITLE = {
    "topic": "AI создаёт форму антенны",
    "domain": "adaptive-radio",
    "nodes": [{"label": "changing radio conditions", "role": "problem"},
              {"label": "adaptive antenna topology", "role": "method"}],
    "relations": [{"source": "changing radio conditions",
                   "target": "adaptive antenna topology", "type": "requires"}],
}


class WouldMatchNobodyTests(unittest.TestCase):
    def setUp(self):
        self.runtime = build_runtime(":memory:",
                                     allowed_origins=frozenset({"http://127.0.0.1"}),
                                     seed=False)
        self.bridge = RemoteMCPBridge(self.runtime.product)
        self.token = self.runtime.product.register_guest().access_token

    def _prepare(self, thought):
        return self.bridge.tool_prepare_thought(
            self.token, {"authorship": "their_own_words", "thought": thought})

    def test_labels_the_index_cannot_compare_are_refused(self):
        with self.assertRaises(BridgeError) as caught:
            self._prepare(RUSSIAN)
        said = str(caught.exception)
        self.assertIn("match nobody", said)
        # It names the labels, so the caller does not have to guess which.
        self.assertIn("адаптивная топология", said)
        # And says what to do instead.
        self.assertIn("English", said)

    def test_the_title_a_person_reads_stays_in_their_language(self):
        prepared = self._prepare(ENGLISH_LABELS_RUSSIAN_TITLE)
        shown = prepared["will_become_discoverable"]["presentation"]["topic"]
        self.assertEqual(shown, "AI создаёт форму антенны")

    def test_every_script_the_semantics_cannot_read_is_covered(self):
        for label in ("メタ安定な状態", "준안정 상태", "亚稳态", "μετασταθής",
                      "מצב מטא-יציב", "حالة شبه مستقرة", "अर्धस्थायी अवस्था"):
            with self.subTest(label):
                thought = {"nodes": [{"label": label, "role": "problem"},
                                     {"label": "a settled state", "role": "outcome"}],
                           "relations": [{"source": label, "target": "a settled state",
                                          "type": "causes"}]}
                with self.assertRaises(BridgeError):
                    self._prepare(thought)

    def test_ordinary_english_is_untouched(self):
        prepared = self._prepare({
            "topic": "Retry storm overloads the queue", "domain": "distributed-systems",
            "nodes": [{"label": "a partial outage", "role": "problem"},
                      {"label": "jittered backoff", "role": "method"}],
            "relations": [{"source": "jittered backoff", "target": "a partial outage",
                           "type": "prevents"}]})
        self.assertEqual(prepared["structure"]["nodes"], 2)

    def test_accented_latin_is_not_mistaken_for_another_script(self):
        """A café is still comparable; only scripts the lexicon cannot read
        are refused, and over-refusing would be its own silent exclusion."""
        prepared = self._prepare({
            "nodes": [{"label": "naive caching", "role": "problem"},
                      {"label": "a café queue", "role": "outcome"}],
            "relations": [{"source": "naive caching", "target": "a café queue",
                           "type": "causes"}]})
        self.assertEqual(prepared["structure"]["nodes"], 2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
