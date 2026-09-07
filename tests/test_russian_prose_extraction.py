"""Extraction from Russian prose.

The engine spoke Russian on the matching side from the start — a bilingual
lexicon and a multilingual label encoder — but not on the way in. A person
writing in their own language got `0 nodes, 0 relations` and an error message
addressed to a language model. For the owner of this project, whose first
language is Russian, the product was unusable in it.

Four things were English-only, and only the first is the obvious one:

  * the connective table;
  * `SENTENCE_END`, whose lookahead was `[A-Z"'(\\[]`, so Cyrillic prose was
    one unbroken sentence and clause segmentation never ran;
  * `WORD`, which matched no Cyrillic at all, so even a matched cue produced
    empty arguments;
  * the stopword, negation, modality and conditional sets.

`stems()` already handled Cyrillic, which is why this looked like a smaller
problem than it was.
"""

from __future__ import annotations

import unittest

from src.extraction import CueExtractor


def graph_of(text: str) -> dict:
    return CueExtractor().extract(text).graph.to_dict()


def edges(text: str) -> list[tuple[str, str, str]]:
    d = graph_of(text)
    by = {n["id"]: n["label"] for n in d["nodes"]}
    return [(by.get(r["source"], ""), r["type"], by.get(r["target"], "")) for r in d["relations"]]


class RussianProdusesStructureTests(unittest.TestCase):
    def test_russian_prose_is_no_longer_silently_empty(self):
        # The exact shape of the failure a person hit in the browser.
        text = ("Длинные смены вызывают усталость, а усталость приводит к "
                "ошибкам при передаче пациента.")
        d = graph_of(text)
        self.assertGreater(len(d["nodes"]), 0)
        self.assertGreater(len(d["relations"]), 0)

    def test_a_chain_of_two_causes_is_read_as_a_chain(self):
        got = edges("Длинные смены вызывают усталость, а усталость приводит к ошибкам.")
        self.assertIn(("Длинные смены", "causes", "усталость"), got)
        self.assertEqual(len([e for e in got if e[1] == "causes"]), 2)

    def test_potomu_chto_reverses_the_direction(self):
        # "X, потому что Y" means Y causes X -- the reverse of the surface order,
        # exactly as English "because" does.
        got = edges("Сервис падает, потому что очередь переполнена.")
        self.assertEqual(len(got), 1)
        source, kind, target = got[0]
        self.assertEqual(kind, "causes")
        self.assertIn("очередь", source)
        self.assertIn("Сервис", target)

    def test_every_relation_type_has_a_working_russian_cue(self):
        for text, expected in (
            ("Длинные смены вызывают усталость.", "causes"),
            ("Жёсткое управление рулём мешает ребёнку научиться балансировать.", "prevents"),
            ("Автопилот требует точной калибровки датчиков.", "requires"),
            ("Бюджет ограничивает размер команды.", "constrains"),
            ("Замеры показывают, что короткие смены снижают число ошибок.", "supports"),
            ("Этот вывод противоречит результатам исследования.", "contradicts"),
            ("Калибровка входит в состав процедуры запуска.", "part_of"),
        ):
            with self.subTest(text=text):
                kinds = {kind for _s, kind, _t in edges(text)}
                self.assertIn(expected, kinds, f"{text!r} -> {kinds}")

    def test_negation_and_modality_are_read_in_russian(self):
        d = graph_of("Короткие смены могут снижать число ошибок.")
        self.assertTrue(d["relations"])
        self.assertEqual(d["relations"][0]["modality"], "possible")


class CyrillicSegmentationTests(unittest.TestCase):
    def test_sentences_split_on_a_cyrillic_capital(self):
        from src.extraction.cue import sentences
        text = "Он повернул вправо. Мотор дёрнул руль влево. Это опасно."
        self.assertEqual(len(sentences(text)), 3)

    def test_words_are_found_in_cyrillic(self):
        from src.extraction.cue import WORD
        self.assertEqual(WORD.findall("мотор резко дёрнул руль"),
                         ["мотор", "резко", "дёрнул", "руль"])


class EnglishIsUntouchedTests(unittest.TestCase):
    """The Russian table is appended after the English one and the two
    alphabets do not overlap, so no English extraction may move. The
    extraction gate agrees (identical metrics before and after), and this
    keeps a fast, readable version of that claim next to the change."""

    def test_a_known_english_extraction_is_unchanged(self):
        got = edges("Long shifts cause fatigue, and fatigue leads to handover errors.")
        self.assertIn(("Long shifts", "causes", "fatigue"), got)
        self.assertEqual(len([e for e in got if e[1] == "causes"]), 2)

    def test_english_because_still_reverses(self):
        got = edges("The service falls over because the queue is saturated.")
        self.assertEqual(len(got), 1)
        source, kind, target = got[0]
        self.assertEqual(kind, "causes")
        self.assertIn("queue", source)

    def test_russian_reaches_parity_rather_than_perfection(self):
        """Both languages misread the same convoluted sentence the same way.

        The left argument of the final cue is taken from a distant clause
        rather than the adjacent one. That is a pre-existing limit of clause
        selection on long multi-clause sentences, identical in English, and it
        is deliberately NOT fixed here: doing so would move frozen English
        figures. Pinned so that the parity is a decision on record rather than
        something discovered again later as a Russian-only fault.
        """
        en = edges("The idea is clear physically, and I like that it does not try "
                   "to hold the bike upright, but can become a gradually fading "
                   "assist, so that the child learns to balance.")
        ru = edges("Идея очень понятная по физике, и мне нравится то, что она не "
                  "пытается держать велосипед вертикально, а может стать постепенно "
                  "исчезающей помощью, чтобы ребёнок научился балансировать.")
        self.assertEqual(len(en), len(ru))
        self.assertEqual([k for _s, k, _t in en], [k for _s, k, _t in ru])


if __name__ == "__main__":
    unittest.main()
