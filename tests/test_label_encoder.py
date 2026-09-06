"""The label encoder adds relatedness the lexicon cannot see, and nothing else.

Measured before this existed, on a solo-sailing thought: "single-handed
fatigue" against "sleep deprivation" scored 0.03, "wind vane self-steering"
against "autopilot" 0.0, and the same trip described twice in different
words came back "negative" at structural 1.00. The lexicon reads seven
hundred phrases; people use more.

These tests run without a model file: a stub encoder stands in, so what is
pinned is the contract -- how a cosine becomes a signal, that the signal only
ever raises what the lexicon gave, that switching encoders forgets cached
answers, and that a deployment says which encoder it runs.
"""

from __future__ import annotations

import unittest

import src.alignment  # noqa: F401  (import order: breaks a circular import)
from src.semantics import compare, neural
from src.semantics.similarity import NEURAL_SAME_WORDS


class StubEncoder:
    """Vectors chosen so that cosines are exactly the numbers in the table."""

    name = "stub-encoder/test"

    def __init__(self, table):
        self.table = table

    def embed(self, label):
        # Not used: relatedness() is what compare() reads, and the stub
        # answers it through `cosine_for` below.
        raise AssertionError("the stub answers cosines directly")


class _Patched:
    """Install a cosine table as the active encoder for the duration."""

    def __init__(self, table):
        self.table = {frozenset(k): v for k, v in table.items()}

    def __enter__(self):
        self._cosine = neural.cosine
        self._embed_holder = neural.OnnxLabelEmbedder

        class Fake:
            name = "stub-encoder/test"

            def embed(inner, label):
                return label  # the "vector" is the label itself

        neural.cosine = lambda a, b: self.table.get(frozenset((a, b)), 0.0)
        neural.activate(Fake())
        return self

    def __exit__(self, *exc):
        neural.cosine = self._cosine
        neural.activate(None)


class RescaleTests(unittest.TestCase):
    def test_the_useful_range_is_the_only_range(self):
        self.assertEqual(neural.rescale(neural.COSINE_FLOOR), 0.0)
        self.assertEqual(neural.rescale(neural.COSINE_FLOOR - 0.1), 0.0)
        self.assertEqual(neural.rescale(neural.COSINE_CEILING), 1.0)
        mid = (neural.COSINE_FLOOR + neural.COSINE_CEILING) / 2
        self.assertAlmostEqual(neural.rescale(mid), 0.5, places=6)

    def test_without_an_encoder_relatedness_is_silent(self):
        neural.activate(None)
        self.assertEqual(neural.relatedness("a", "b"), 0.0)
        self.assertIsNone(neural.active())


class FusionTests(unittest.TestCase):
    def test_a_paraphrase_the_lexicon_missed_becomes_related(self):
        before = compare("single-handed fatigue", "sleep deprivation")
        self.assertLess(before.fused, 0.1)
        with _Patched({("single-handed fatigue", "sleep deprivation"): 0.86}):
            after = compare("single-handed fatigue", "sleep deprivation")
        expected = neural.rescale(0.86)
        self.assertAlmostEqual(after.concept, expected, places=6)
        self.assertGreaterEqual(after.fused, 0.9 * expected)
        # the words are different, and the encoder was not sure enough to say
        # otherwise: surface stays what the lexicon measured
        self.assertLess(expected, NEURAL_SAME_WORDS)
        self.assertAlmostEqual(after.surface, before.surface, places=6)

    def test_a_near_identical_label_counts_as_the_same_words(self):
        with _Patched({("solo passage to Hawaii", "sailing alone to Hawaii"): 0.92}):
            said = compare("solo passage to Hawaii", "sailing alone to Hawaii")
        self.assertGreaterEqual(neural.rescale(0.92), NEURAL_SAME_WORDS)
        self.assertGreaterEqual(said.surface, NEURAL_SAME_WORDS)

    def test_the_encoder_never_lowers_what_the_lexicon_gave(self):
        before = compare("heat accumulation", "backlog pileup")   # lexicon: same concept
        with _Patched({("heat accumulation", "backlog pileup"): 0.5}):   # encoder: unrelated
            after = compare("heat accumulation", "backlog pileup")
        self.assertGreaterEqual(after.concept, before.concept)
        self.assertGreaterEqual(after.fused, before.fused)

    def test_switching_encoders_forgets_cached_answers(self):
        with _Patched({("x one", "y two"): 0.9}):
            first = compare("x one", "y two").fused
        self.assertGreater(first, 0.5)
        self.assertLess(compare("x one", "y two").fused, 0.5)   # encoder gone


class DeploymentTests(unittest.TestCase):
    def test_an_unset_variable_means_no_encoder(self):
        self.assertIsNone(neural.activate_from_environment({}))
        self.assertIsNone(neural.active())

    def test_a_bad_directory_is_refused_out_loud(self):
        with self.assertRaises(neural.NeuralUnavailable):
            neural.activate_from_environment({neural.ENV_VAR: "/nowhere/at/all"})

    def test_the_engine_identity_names_the_encoder(self):
        from src.product.server import build_runtime, engine_identity
        runtime = build_runtime(":ephemeral:", allowed_origins=frozenset({"x"}), seed=False)
        with _Patched({}):
            self.assertEqual(engine_identity(runtime)["label_encoder"], "stub-encoder/test")
        self.assertIsNone(engine_identity(runtime)["label_encoder"])


if __name__ == "__main__":
    unittest.main()
