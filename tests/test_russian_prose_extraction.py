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


class NoNonsenseNodesTests(unittest.TestCase):
    """Found by the owner reading his own card: it said «что --causes--> ребёнок».

    Two mistakes met. The first draft of the Russian table mapped English
    `makes|made|make` onto «делает|делают|сделал» -- a false friend. English
    "makes" is causal only in "makes X happen"; Russian «делает» is the
    ordinary verb "does", so «к тому, что делает ребёнок» ("to what the child
    does") was read as a causal claim. The second is that nothing stopped a
    bare complementiser from becoming a node once a cue landed beside it.

    A wrong relation is worse than a missing one here: the whole promise is
    that the structure shown is the person's own reasoning.
    """

    def test_delaet_is_not_treated_as_a_causal_cue(self):
        text = ("Я бы делала steering assist: система добавляет ограниченный "
                "момент к тому, что делает ребёнок, но никогда полностью не "
                "забирает управление.")
        self.assertEqual(edges(text), [],
                         "no explicit causal connective here, so nothing may be claimed")

    def test_a_bare_function_word_is_never_a_node(self):
        junk = {"что", "чего", "чем", "кто", "как", "где", "когда", "том", "то"}
        for text in (
            "Система добавляет момент к тому, что делает ребёнок.",
            "Важно то, что ребёнок учится сам.",
            "Непонятно, кто вызывает ошибку.",
        ):
            with self.subTest(text=text):
                labels = {n["label"].strip().lower() for n in graph_of(text)["nodes"]}
                self.assertEqual(labels & junk, set(), f"{text!r} -> {labels}")

    def test_a_real_causal_claim_in_the_same_document_still_reads(self):
        # Removing the false friend must not cost the relations that were right.
        got = edges("Мотор через пружинную муфту создаёт небольшой корректирующий момент.")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][1], "causes")


class ConnectivesAreNotThingsTests(unittest.TestCase):
    """Second round of the same complaint, from the same person, on the same card.

    After «что» stopped becoming a node, «поэтому» started heading one:
    «поэтому система --prevents--> вмешательство». A discourse connective joins
    clauses; it is never the head of the thing being reasoned about.

    English has the same hole — `therefore`, `hence` and `thus` are absent from
    `LEADING_DROP` too — but its gold never lands on it, so only the Cyrillic
    side is filled and the English figures stay identical.
    """

    def test_a_connective_does_not_head_a_label(self):
        text = ("Постоянная помощь мешает ребёнку научиться балансировать, "
                "поэтому система постепенно уменьшает вмешательство.")
        labels = [n["label"] for n in graph_of(text)["nodes"]]
        for label in labels:
            self.assertFalse(label.lower().startswith(("поэтому", "следовательно", "иначе", "однако")),
                             f"a connective headed a node label: {label!r}")

    def test_a_relation_may_not_restate_one_end_in_the_other(self):
        """Unification by stem containment could relate a thing to a sentence
        containing it, which a person read as «Постоянная помощь --prevents-->
        Постоянная помощь мешает ребёнку научиться балансировать». Nothing is
        claimed by that, so it is abstained rather than shown.

        This one is not Cyrillic-scoped — it applies to both languages — and
        the extraction gate is unchanged by it, so English never produced one.
        """
        text = ("Постоянная помощь мешает ребёнку научиться балансировать, "
                "поэтому система постепенно уменьшает вмешательство.")
        d = graph_of(text)
        by = {n["id"]: n["label"] for n in d["nodes"]}
        from src.semantics import stems
        for r in d["relations"]:
            a, b = set(stems(by[r["source"]])), set(stems(by[r["target"]]))
            self.assertFalse(a < b or b < a,
                             f"{by[r['source']]!r} --{r['type']}--> {by[r['target']]!r}")


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
