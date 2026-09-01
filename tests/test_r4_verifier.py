"""R4 verifier unit tests: protocol conformance, ADR-0003 hard rules,
determinism, path guards, and frozen-interface invariants."""

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.graph import ThoughtGraph
from src.interfaces import SeedCorrespondence, StructuralVerifier, VerifierResult
from src.alignment import DEFAULT_CONFIG, MultiRelFGWVerifier, RRWMVerifier

V01 = REPO / "benchmark" / "r0-v0.1"


def load_fixtures():
    graphs = {}
    for line in (V01 / "graphs.jsonl").read_text().splitlines():
        d = json.loads(line)
        graphs[d["benchmark_graph_id"]] = ThoughtGraph.from_dict(d["thought_dna"])
    pairs = [json.loads(line) for line in (V01 / "pairs.jsonl").read_text().splitlines()]
    return graphs, pairs


GRAPHS, PAIRS = load_fixtures()


def pair_of(family, subtype=None):
    for p in PAIRS:
        if p["family"] != family:
            continue
        if subtype and p["transform_manifest"].get("negative_subtype") != subtype:
            continue
        return p
    raise AssertionError(family)


class ProtocolTests(unittest.TestCase):
    def test_verifiers_satisfy_structural_verifier_protocol(self):
        self.assertIsInstance(MultiRelFGWVerifier(), StructuralVerifier)
        self.assertIsInstance(RRWMVerifier(), StructuralVerifier)

    def test_result_is_a_valid_frozen_verifier_result(self):
        p = pair_of("paraphrase")
        r = MultiRelFGWVerifier().verify(GRAPHS[p["query_graph"]], GRAPHS[p["candidate_graph"]])
        self.assertIsInstance(r, VerifierResult)          # frozen-type invariants ran
        self.assertEqual(r.contract_version, "resonance-score/0.1")
        self.assertFalse(r.retrieval_flags.polarity_reliable)
        self.assertTrue(r.retrieval_flags.requires_structural_verification)
        wire = r.components.to_wire()                     # round-trips the score contract
        self.assertIn("structural_score", wire)

    def test_identity_pair_maps_fully_with_direct_class(self):
        p = pair_of("serialization_permutation")
        r = MultiRelFGWVerifier().verify(GRAPHS[p["query_graph"]], GRAPHS[p["candidate_graph"]])
        self.assertEqual(r.classification, "direct")
        gold = {tuple(x) for x in p["gold_node_pairs"]}
        got = {(m.query_node, m.candidate_node) for m in r.mapping}
        self.assertEqual(got, gold)


class HardRuleTests(unittest.TestCase):
    def test_polarity_flip_is_hard_rejected(self):
        p = pair_of("same_vocabulary_wrong_structure", "polarity_flip")
        r = MultiRelFGWVerifier().verify(GRAPHS[p["query_graph"]], GRAPHS[p["candidate_graph"]])
        self.assertIsNotNone(r.hard_rejection)
        self.assertTrue(r.components.h_sign_conflict)
        self.assertEqual(r.components.structural, 0.0)
        self.assertEqual(r.classification, "negative")

    def test_direction_reversal_is_hard_rejected(self):
        p = pair_of("same_vocabulary_wrong_structure", "direction_reversal")
        r = MultiRelFGWVerifier().verify(GRAPHS[p["query_graph"]], GRAPHS[p["candidate_graph"]])
        self.assertIsNotNone(r.hard_rejection)
        self.assertEqual(r.classification, "negative")

    def test_cross_domain_analogy_survives_low_semantics(self):
        p = pair_of("cross_domain_analogy")
        r = MultiRelFGWVerifier().verify(GRAPHS[p["query_graph"]], GRAPHS[p["candidate_graph"]])
        self.assertEqual(r.classification, "analogical")
        self.assertLess(r.components.semantic, 0.3)
        self.assertGreaterEqual(r.components.structural, 0.85)

    def test_generic_motif_distractor_is_not_called_analogical(self):
        p = pair_of("generic_motif_distractor")
        r = MultiRelFGWVerifier().verify(GRAPHS[p["query_graph"]], GRAPHS[p["candidate_graph"]])
        self.assertEqual(r.classification, "negative")

    def test_contradiction_witness_stays_mapped(self):
        """The verifier must report the conflict, not un-claim the witness."""
        p = pair_of("same_vocabulary_wrong_structure", "polarity_flip")
        r = MultiRelFGWVerifier().verify(GRAPHS[p["query_graph"]], GRAPHS[p["candidate_graph"]])
        conflicted_nodes = set()
        rel_by_id = {rel.id: rel for rel in GRAPHS[p["query_graph"]].relations}
        for con in r.contradictions:
            rel = rel_by_id[con.query_item]
            conflicted_nodes.update((rel.source, rel.target))
        mapped_q = {m.query_node for m in r.mapping}
        self.assertTrue(conflicted_nodes <= mapped_q)


class DeterminismTests(unittest.TestCase):
    def test_two_runs_are_identical(self):
        p = pair_of("modest_extraction_error")
        a = MultiRelFGWVerifier().verify(GRAPHS[p["query_graph"]], GRAPHS[p["candidate_graph"]])
        b = MultiRelFGWVerifier().verify(GRAPHS[p["query_graph"]], GRAPHS[p["candidate_graph"]])
        self.assertEqual(a, b)

    def test_seeds_do_not_remove_the_unseeded_restart(self):
        p = pair_of("paraphrase")
        q, c = GRAPHS[p["query_graph"]], GRAPHS[p["candidate_graph"]]
        wrong_seed = [SeedCorrespondence(query_node=q.nodes[0].id,
                                         candidate_node=c.nodes[-1].id,
                                         support=1.0, channel="structural")]
        seeded = MultiRelFGWVerifier().verify(q, c, seeds=wrong_seed)
        unseeded = MultiRelFGWVerifier().verify(q, c)
        # a deliberately wrong seed must not degrade the final mapping: the
        # mandatory unseeded restart wins selection (ADR-0003).
        self.assertEqual(
            {(m.query_node, m.candidate_node) for m in seeded.mapping},
            {(m.query_node, m.candidate_node) for m in unseeded.mapping})


class PathGuardTests(unittest.TestCase):
    def test_transparent_granularity_gets_guarded_path_credit(self):
        p = pair_of("transparent_granularity")
        r = MultiRelFGWVerifier().verify(GRAPHS[p["query_graph"]], GRAPHS[p["candidate_graph"]])
        self.assertGreater(r.components.r_path, 0.0)
        for match in r.edge_path_matches:
            self.assertGreaterEqual(len(match.candidate_relations), 2)
            self.assertLessEqual(len(match.candidate_relations), 4)
            self.assertEqual(len(match.realizes_nodes),
                             len(match.candidate_relations) - 1)

    def test_path_matching_off_reports_zero_r_path(self):
        p = pair_of("transparent_granularity")
        r = MultiRelFGWVerifier({"path_matching": "off"}).verify(
            GRAPHS[p["query_graph"]], GRAPHS[p["candidate_graph"]])
        self.assertEqual(r.components.r_path, 0.0)
        self.assertEqual(r.edge_path_matches, ())

    def test_config_hash_distinguishes_configurations(self):
        a = MultiRelFGWVerifier()
        b = MultiRelFGWVerifier({"path_matching": "off"})
        self.assertNotEqual(a.config_hash, b.config_hash)
        self.assertEqual(a.config_hash, MultiRelFGWVerifier(dict(DEFAULT_CONFIG)).config_hash)


class GateCandidateTests(unittest.TestCase):
    def test_rrwm_agrees_on_hard_negatives_and_analogy(self):
        v = RRWMVerifier()
        p = pair_of("same_vocabulary_wrong_structure", "polarity_flip")
        self.assertEqual(v.verify(GRAPHS[p["query_graph"]], GRAPHS[p["candidate_graph"]]).classification,
                         "negative")
        p = pair_of("cross_domain_analogy")
        self.assertEqual(v.verify(GRAPHS[p["query_graph"]], GRAPHS[p["candidate_graph"]]).classification,
                         "analogical")


if __name__ == "__main__":
    unittest.main()


class KnowledgeRuleTests(unittest.TestCase):
    """Scoring v0.1 knowledge branch fires when both sides carry `about` ids."""

    @staticmethod
    def _graph(tid, about_id):
        import hashlib
        text = f"knowledge fixture {tid}"
        return ThoughtGraph.from_dict({
            "schema_version": "thought-dna/0.1", "thought_id": tid,
            "provenance": {"kind": "manual", "human_id": "test", "extractor": None},
            "source": {"text": text,
                       "sha256": hashlib.sha256(text.encode()).hexdigest()},
            "nodes": [
                {"id": "n0", "label": "alpha driver", "role": "state", "spans": [],
                 "extract_conf": 1.0, "atomic": True,
                 "knowledge": {"about": [{"id": about_id, "conf": 1.0}], "requires": []}},
                {"id": "n1", "label": "beta pressure", "role": "mechanism", "spans": [],
                 "extract_conf": 1.0, "atomic": True},
                {"id": "n2", "label": "gamma load", "role": "state", "spans": [],
                 "extract_conf": 1.0, "atomic": True},
                {"id": "n3", "label": "delta strain", "role": "mechanism", "spans": [],
                 "extract_conf": 1.0, "atomic": True},
                {"id": "n4", "label": "epsilon drift", "role": "state", "spans": [],
                 "extract_conf": 1.0, "atomic": True},
                {"id": "n5", "label": "zeta collapse", "role": "outcome", "spans": [],
                 "extract_conf": 1.0, "atomic": True},
            ],
            "relations": [
                {"id": "r0", "source": "n0", "target": "n1", "type": "causes",
                 "extract_conf": 1.0, "spans": []},
                {"id": "r1", "source": "n1", "target": "n2", "type": "increases"
                 if False else "supports", "extract_conf": 1.0, "spans": []},
                {"id": "r2", "source": "n2", "target": "n3", "type": "causes",
                 "extract_conf": 1.0, "spans": []},
                {"id": "r3", "source": "n3", "target": "n4", "type": "prevents",
                 "extract_conf": 1.0, "spans": []},
                {"id": "r4", "source": "n4", "target": "n5", "type": "causes",
                 "extract_conf": 1.0, "spans": []},
            ]})

    def test_shared_about_ids_yield_direct_or_approximate(self):
        a = self._graph("ka", "wd:Q1")
        b = self._graph("kb", "wd:Q1")
        r = MultiRelFGWVerifier().verify(a, b)
        self.assertTrue(r.components.knowledge_evidence_present)
        self.assertIn(r.classification, ("direct", "approximate"))

    def test_disjoint_about_ids_yield_analogical(self):
        a = self._graph("ka", "wd:Q1")
        b = self._graph("kb", "wd:Q2")
        r = MultiRelFGWVerifier().verify(a, b)
        self.assertEqual(r.classification, "analogical")
