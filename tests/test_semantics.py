"""Deterministic label semantics: stems, concepts, similarity, PII scrub."""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.semantics import (  # noqa: E402
    abstract_concepts, compare, concepts, contains_pii, domain_concepts, label_similarity,
    role_hint, scrub, stem, stems, surface_similarity,
)
from src.semantics.embedding import HashedFeatureEmbedder, cosine, label_vector  # noqa: E402


class StemTests(unittest.TestCase):
    def test_inflections_share_a_stem(self):
        self.assertEqual(stem("accumulates"), stem("accumulation"))
        self.assertEqual(stem("degrades"), stem("degradation"))
        self.assertEqual(stem("retries"), stem("retried"))

    def test_stopwords_are_dropped(self):
        self.assertEqual(stems("the heat of the cell"), ("heat", "cell"))


class ConceptTests(unittest.TestCase):
    def test_multiword_phrases_resolve(self):
        self.assertIn("ACCUMULATION", concepts("data pile up in the inbox"))
        self.assertIn("CASCADE", concepts("margin-call cascade"))
        self.assertIn("COOLING", concepts("thermal control"))

    def test_domain_classes_are_separated_from_abstract_ones(self):
        self.assertIn("DOMAIN_ELECTROCHEMISTRY", domain_concepts("battery cell"))
        self.assertNotIn("DOMAIN_ELECTROCHEMISTRY", abstract_concepts("battery cell"))

    def test_role_hint_follows_lexicon(self):
        self.assertEqual(role_hint("cell failure"), "outcome")
        self.assertEqual(role_hint("active cooling"), "method")
        self.assertIsNone(role_hint("wedding venue"))


class SimilarityTests(unittest.TestCase):
    def test_paraphrase_is_surface_similar(self):
        self.assertGreaterEqual(surface_similarity("rephrased high cell heat", "high cell heat"), 0.7)

    def test_cross_domain_analogy_is_concept_similar_but_not_surface_similar(self):
        r = compare("battery failure", "organizational collapse")
        self.assertEqual(r.surface, 0.0)
        self.assertGreaterEqual(r.concept, 0.9)
        self.assertGreaterEqual(r.fused, 0.8)

    def test_related_concepts_get_partial_credit(self):
        r = compare("retry amplification", "margin-call cascade")
        self.assertGreater(r.concept, 0.2)
        self.assertLess(r.concept, 0.7)

    def test_unrelated_labels_score_zero(self):
        self.assertEqual(label_similarity("wedding venue booking", "heat accumulation"), 0.0)

    def test_similarity_is_symmetric_and_bounded(self):
        for a, b in (("heat accumulation", "backlog pileup"), ("x", "y"), ("cooling", "thermal control")):
            self.assertAlmostEqual(label_similarity(a, b), label_similarity(b, a))
            self.assertLessEqual(label_similarity(a, b), 1.0)
            self.assertGreaterEqual(label_similarity(a, b), 0.0)


class PIITests(unittest.TestCase):
    def test_contact_details_are_removed(self):
        text = "ask bob@acme.com or +1 (555) 123-4567, see https://x.y/z or @bobby"
        self.assertTrue(contains_pii(text))
        out = scrub(text)
        self.assertFalse(contains_pii(out))
        self.assertNotIn("acme", out)
        self.assertNotIn("555", out)

    def test_plain_labels_are_untouched(self):
        self.assertEqual(scrub("heat accumulation"), "heat accumulation")


class EmbeddingSeamTests(unittest.TestCase):
    def test_default_embedder_is_deterministic_and_orders_like_compare(self):
        a = label_vector("heat accumulation")
        self.assertEqual(a, HashedFeatureEmbedder().embed("heat accumulation"))
        near = cosine(a, label_vector("backlog pileup"))
        far = cosine(a, label_vector("wedding venue booking"))
        self.assertGreater(near, far)


if __name__ == "__main__":
    unittest.main()
