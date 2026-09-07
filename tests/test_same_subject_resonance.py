"""Two people on the same subject must not be told they do not resonate.

Every number here was measured on production on 2026-09-06, on the first pair
of real thoughts the product ever matched: a registry of employer conduct
towards candidates against a registry of landlord conduct towards tenants.
Both people had independently reached the same construction -- private
scattered conduct, a blind decision, no cost to the stronger party, repetition,
a shared registry making conduct visible before the decision, and a cold start
that needs an organisation with histories already in hand.

The engine returned `negative` for that pair, and returned a template
coincidence ("overtime in a ward") ABOVE it.
"""

from __future__ import annotations

import unittest

from src.engine.facade import _rank_score  # imported first: it pulls the
from src import scoring                     # package graph in a working order


def _components(**over):
    """A full component set; defaults are the neutral values classify() reads."""
    base = {
        "structural": 0.0, "semantic": 0.0, "r_direct": 0.0, "y_systematicity": 0.0,
        "coverage_containment": 0.0, "coverage_symmetric": 0.0, "contradiction": 0.0,
        "h_sign_conflict": False, "n_role_exact": 1.0, "evidence_gate": 1.0,
        "complement_query_to_candidate": 0.0, "complement_candidate_to_query": 0.0,
        "surface_semantic": 0.0, "domain_overlap": 0.0, "concept_alignment": 0.0,
        "knowledge_about": 0.0, "rarity": 0.0, "rarity_weighting": False,
    }
    base.update(over)
    return base


# Measured on production, `resonance_explain_match`, September 2026.
TWIN = _components(
    structural=0.18639830673753915, semantic=0.590270812633428,
    r_direct=0.14285714285714285, y_systematicity=0.5,
    coverage_containment=1.0, contradiction=0.21428571428571427,
    h_sign_conflict=False, surface_semantic=0.35, concept_alignment=0.30,
)
COINCIDENCE = _components(
    structural=0.3054713471803808, semantic=0.12006728592741399,
    r_direct=0.1285714285714286, y_systematicity=1.0,
    coverage_containment=1.0, contradiction=0.0, h_sign_conflict=False,
)


class SameSubjectTests(unittest.TestCase):
    def test_the_real_pair_is_no_longer_called_negative(self):
        """Semantic agreement 0.59 with one crossed correspondence is a
        disagreement about ordering, not an absence of resonance."""
        self.assertNotEqual(scoring.classify(TWIN), "negative")

    def test_a_crossed_correspondence_alone_does_not_reject(self):
        """The branch used to demand `contradiction == 0.0` exactly, so a
        single crossed pair dropped the couple back to the strangers' bar."""
        crossed = dict(TWIN, contradiction=0.0)
        self.assertEqual(scoring.classify(crossed), scoring.classify(TWIN))

    def test_the_template_coincidence_stays_negative(self):
        """Shape without meaning is still nothing: 0.31 structural on 0.12
        semantic is a skeleton that happens to line up."""
        self.assertEqual(scoring.classify(COINCIDENCE), "negative")

    def test_a_real_polarity_conflict_is_still_refused(self):
        """Widening the contradiction ceiling must not admit the pair that
        says causes where the other says prevents."""
        conflicted = dict(TWIN, h_sign_conflict=True)
        self.assertEqual(scoring.classify(conflicted), "negative")

    def test_wild_contradiction_is_still_refused(self):
        """Same subject buys tolerance, not immunity."""
        wild = dict(TWIN, contradiction=0.9)
        self.assertEqual(scoring.classify(wild), "negative")

    def test_meaning_outranks_a_coincidence(self):
        """Ranking read `structural` alone, so the coincidence was returned
        first. Shape alone cannot tell a coincidence from a match."""
        class _V:
            def __init__(self, c):
                self.components = type("C", (), c)
        twin = _rank_score(_V({"structural": TWIN["structural"], "semantic": TWIN["semantic"]}))
        coincidence = _rank_score(
            _V({"structural": COINCIDENCE["structural"], "semantic": COINCIDENCE["semantic"]}))
        self.assertGreater(twin, coincidence)


class SameDomainTests(unittest.TestCase):
    """Two people can be in the SAME field thinking about the SAME thing --
    two solo sailors, different oceans and different routes. That is the
    common case, not the exotic one, and it must not need a different domain
    to be found."""

    def test_same_subject_partial_overlap_resonates(self):
        pair = _components(
            structural=0.22, semantic=0.62, r_direct=0.30, y_systematicity=0.6,
            coverage_containment=0.7, contradiction=0.10, surface_semantic=0.55,
            domain_overlap=0.80, concept_alignment=0.45,
        )
        verdict = scoring.classify(pair)
        self.assertIn(verdict, ("direct", "approximate"))
        self.assertNotEqual(verdict, "negative")

    def test_one_person_holds_a_piece_of_the_other_problem(self):
        """Whole-graph structure falls as one person's picture grows; the
        person working inside your problem must still be found."""
        piece = _components(
            structural=0.17, semantic=0.55, r_direct=0.25, coverage_containment=1.0,
            surface_semantic=0.50, domain_overlap=0.70, concept_alignment=0.40,
        )
        self.assertNotEqual(scoring.classify(piece), "negative")


if __name__ == "__main__":
    unittest.main()


class EvidenceNotJudgementTests(unittest.TestCase):
    """A verdict is this engine's opinion, not the truth about two people.

    Rows the classifier called `negative` were dropped from what a person is
    told, so on 2026-09-06 someone was told "nothing the engine calls a
    resonance" about a person who had independently built the same
    construction step for step. VISION.md says the opposite is the point:
    provide evidence, not social judgement, and let people decide with a
    better signal.
    """

    def _result(self, rows):
        return {"matches_in_backend_order": rows, "rejected": [], "shape_note": ""}

    def _row(self, pseudonym, semantic, topic, verdict="negative", ideas=11, links=2):
        return {"person_pseudonym": pseudonym, "mode_classification": verdict,
                "hard_rejection": None, "scores": {"structural": 0.19, "semantic": semantic},
                "evidence": {"mapped_node_count": ideas, "preserved_relation_count": links,
                             "contradiction_count": 4},
                "display": {"topic": topic}}

    def test_a_near_miss_with_real_meaning_is_shown_not_hidden(self):
        from src.product import phrasing
        said = phrasing.say("resonance_discover", self._result([
            self._row("Fleet Minstrel", 0.59, "Shared landlord history before signing")]))
        self.assertIn("Fleet Minstrel", said)
        self.assertIn("Shared landlord history", said)
        self.assertIn("may be wrong", said)
        self.assertNotIn("nobody is being suggested", said)

    def test_a_coincidence_without_meaning_is_still_not_offered(self):
        """Showing everything would be as useless as showing nothing: the
        template coincidence measured that day agreed on 0.12."""
        from src.product import phrasing
        said = phrasing.say("resonance_discover", self._result([
            self._row("Fleet Minstrel", 0.12, "Protected handover time on a ward")]))
        self.assertNotIn("Protected handover time", said)
        self.assertIn("Nothing the engine calls a resonance", said)

    def test_the_bar_is_the_engines_own(self):
        """The words a person reads must not drift from the verdict they are
        told about; `phrasing` copies the constant to avoid an import cycle."""
        from src.product import phrasing
        self.assertEqual(phrasing.SAME_SUBJECT_MEANING, scoring.T_SAME_SUBJECT_SEMANTIC)
