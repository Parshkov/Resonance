import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO = Path(__file__).parents[1]
V01 = REPO / "benchmark" / "r0-v0.1"
V02 = REPO / "benchmark" / "r0-v0.2"


def load_runner():
    spec = importlib.util.spec_from_file_location("resonance_benchmark_v02_runner", V02 / "runner.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


runner = load_runner()


def licensed_path(pair):
    for item in pair["gold_edge_pairs"]:
        if isinstance(item[1], list) and len(item[1]) >= 2:
            return item
    return None


def forbidden_path(pair):
    return pair["forbidden_edge_path_matches"][0] if pair["forbidden_edge_path_matches"] else None


def oracle_predictions(bundle):
    records = []
    for pair in bundle.pairs:
        licensed = licensed_path(pair)
        path_matches = []
        if licensed:
            path_matches.append({
                "query_relation": licensed[0],
                "candidate_relations": list(licensed[1]),
                "realizes_nodes": list(pair["transform_manifest"]["interior_nodes"]),
            })
        records.append({
            "case_id": pair["case_id"],
            "retrieval": {
                "candidate_rank": 1,
                "requires_structural_verification": True,
                "polarity_reliable": False,
            },
            "verification": {
                "predicted_class": pair["gold_class"],
                "node_mapping": copy.deepcopy(pair["gold_node_pairs"]),
                "edge_mapping": copy.deepcopy(pair["gold_edge_pairs"]),
                "edge_path_matches": path_matches,
                "false_contractions": 0,
            },
        })
    return records


def cheating_predictions(bundle):
    records = oracle_predictions(bundle)
    by_id = {item["case_id"]: item for item in records}
    atomic = next(pair for pair in bundle.pairs if pair["family"] == "atomic_mediator")
    forbidden = forbidden_path(atomic)
    cheater = by_id[atomic["case_id"]]
    cheater["verification"]["predicted_class"] = "approximate"
    cheater["verification"]["false_contractions"] = 0
    cheater["verification"]["edge_mapping"] = [forbidden]
    cheater["verification"]["edge_path_matches"] = [{
        "query_relation": forbidden[0],
        "candidate_relations": list(forbidden[1]),
        "realizes_nodes": list(atomic["transform_manifest"]["interior_nodes"]),
    }]
    return list(by_id.values())


class FrozenV01IsolationTests(unittest.TestCase):
    def test_v0_1_manifest_hash_is_untouched(self):
        manifest = json.loads((V01 / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["benchmark_version"], "r0-v0.1")
        self.assertEqual(manifest["freeze_state"], "independent_review_complete")
        for relative, expected in manifest["files"].items():
            payload = (V01 / relative).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), expected["sha256"], relative)
            self.assertEqual(len(payload), expected["bytes"], relative)


class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = runner.validate_fixtures()

    def test_counts_and_required_families(self):
        families = {pair["family"] for pair in self.bundle.pairs}
        self.assertEqual(len(self.bundle.pairs), 15)
        self.assertEqual(len(self.bundle.graphs), 16)
        self.assertIn("transparent_one_step", families)
        self.assertIn("transparent_three_steps", families)
        self.assertIn("atomic_mediator", families)
        self.assertIn("meaningful_mediator", families)
        self.assertIn("branch_at_mediator", families)
        self.assertIn("merge_at_mediator", families)
        self.assertIn("sign_flip", families)
        self.assertIn("relation_mixture", families)
        self.assertIn("assertion_boundary", families)
        self.assertIn("modality_boundary", families)
        self.assertIn("path_too_long", families)
        self.assertEqual(sum(pair["relevant"] for pair in self.bundle.pairs), 2)
        self.assertEqual(sum(not pair["relevant"] for pair in self.bundle.pairs), 13)

    def test_preservation_gold_is_present(self):
        for pair in self.bundle.pairs:
            self.assertIn("meaningful_nodes", pair)
            self.assertIn("must_preserve_nodes", pair)
            self.assertIn("forbidden_edge_path_matches", pair)
            if pair["relevant"]:
                self.assertTrue(licensed_path(pair))
                self.assertEqual(pair["must_preserve_nodes"], [])
                self.assertEqual(pair["forbidden_edge_path_matches"], [])
            else:
                self.assertTrue(pair["forbidden_edge_path_matches"])
                self.assertTrue(pair["must_preserve_nodes"])

    def test_meaningful_mediator_is_machine_similar_but_gold_distinct(self):
        by_family = {pair["family"]: pair for pair in self.bundle.pairs}
        transparent = by_family["transparent_one_step"]
        meaningful = by_family["meaningful_mediator"]
        t_graph = self.bundle.graph_by_id[transparent["candidate_graph"]]["thought_dna"]
        m_graph = self.bundle.graph_by_id[meaningful["candidate_graph"]]["thought_dna"]
        t_x0 = next(node for node in t_graph["nodes"] if node["id"] == "x0")
        m_x0 = next(node for node in m_graph["nodes"] if node["id"] == "x0")
        self.assertFalse(t_x0["atomic"])
        self.assertFalse(m_x0["atomic"])
        self.assertEqual(t_x0["role"], "mechanism")
        self.assertEqual(m_x0["role"], "mechanism")
        self.assertEqual(meaningful["meaningful_nodes"], ["x0"])
        self.assertEqual(meaningful["must_preserve_nodes"], ["x0"])
        self.assertNotEqual(transparent["gold_edge_pairs"], meaningful["gold_edge_pairs"])
        self.assertTrue(meaningful["review"]["required"])
        self.assertEqual(meaningful["review"]["status"], "pending")
        self.assertIsNone(meaningful["review"]["reviewer"])
        self.assertNotEqual(meaningful["review"]["reviewer"], "parshkov-xai-grok46-k3e8")

    def test_gold_is_not_in_engine_graph_inputs(self):
        forbidden = {
            "gold_class", "gold_node_pairs", "gold_edge_pairs", "relevant", "rationale",
            "review", "family", "must_preserve_nodes", "meaningful_nodes", "forbidden_edge_path_matches",
        }
        for wrapper in self.bundle.graphs:
            serialized = json.dumps(wrapper["thought_dna"], sort_keys=True)
            self.assertTrue(all(f'"{field}"' not in serialized for field in forbidden))

    def test_author_cannot_self_approve_required_gold(self):
        self.assertEqual(self.bundle.manifest["freeze_state"], "candidate_frozen_pending_independent_review")
        self.assertEqual(self.bundle.manifest["counts"]["manual_reviews_pending"], 1)

    def test_cli_validate_is_deterministic(self):
        command = [sys.executable, str(V02 / "runner.py"), "validate"]
        first = subprocess.run(command, cwd=REPO, check=True, capture_output=True, text=True).stdout
        second = subprocess.run(command, cwd=REPO, check=True, capture_output=True, text=True).stdout
        self.assertEqual(first, second)
        payload = json.loads(first)
        self.assertEqual(payload["benchmark_version"], "r0-v0.2")
        self.assertFalse(payload["gate_execution_ready"])


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.bundle = runner.validate_fixtures()

    def test_oracle_passes_derived_contraction_gate_and_transparent_positives(self):
        report = runner.evaluate(self.bundle, oracle_predictions(self.bundle))
        self.assertEqual(report["gates"]["false_meaningful_contractions"]["status"], "pass")
        self.assertEqual(report["gates"]["transparent_positives_pass"]["status"], "pass")
        self.assertEqual(report["gates"]["self_report_ignored"]["status"], "pass")
        self.assertEqual(report["overall_status"], "pass")
        self.assertEqual(report["gates"]["independent_gold_review"]["status"], "fail")

    def test_cheating_self_report_zero_fails_when_mappings_violate_gold(self):
        report = runner.evaluate(self.bundle, cheating_predictions(self.bundle))
        self.assertEqual(report["gates"]["false_meaningful_contractions"]["status"], "fail")
        self.assertGreater(report["gates"]["false_meaningful_contractions"]["value"], 0)
        self.assertEqual(report["overall_status"], "fail")
        self.assertGreaterEqual(report["pipeline_attribution"]["verifier_mapping"], 1)
        atomic = next(row for row in report["cases"] if row["family"] == "atomic_mediator")
        self.assertEqual(atomic["self_reported_false_contractions"], 0)
        self.assertGreater(atomic["derived_false_contractions"], 0)
        self.assertEqual(atomic["stage"], "verifier_mapping")
        self.assertTrue(any("forbidden_edge_path_match" in item["reasons"] for item in atomic["violations"]))

    def test_self_reported_nonzero_cannot_fail_a_licensed_positive(self):
        records = oracle_predictions(self.bundle)
        positive = next(item for item in records if item["case_id"] == "V02-01")
        positive["verification"]["false_contractions"] = 99
        report = runner.evaluate(self.bundle, records)
        self.assertEqual(report["gates"]["false_meaningful_contractions"]["status"], "pass")
        self.assertEqual(report["gates"]["transparent_positives_pass"]["status"], "pass")

    def test_negative_families_are_verifier_mapping_failures(self):
        records = oracle_predictions(self.bundle)
        by_id = {item["case_id"]: item for item in records}
        for pair in self.bundle.pairs:
            if pair["relevant"]:
                continue
            forbidden = forbidden_path(pair)
            item = by_id[pair["case_id"]]
            item["verification"]["edge_path_matches"] = [{
                "query_relation": forbidden[0],
                "candidate_relations": list(forbidden[1]),
                "realizes_nodes": list(pair["transform_manifest"]["interior_nodes"]),
            }]
            item["verification"]["false_contractions"] = 0
        report = runner.evaluate(self.bundle, list(by_id.values()))
        self.assertEqual(report["gates"]["false_meaningful_contractions"]["status"], "fail")
        self.assertEqual(report["pipeline_attribution"]["verifier_mapping"], 13)
        self.assertEqual(report["gates"]["transparent_positives_pass"]["status"], "pass")

    def test_v0_1_transparent_positives_still_pass_read_only_overlay(self):
        v01_pairs = [json.loads(line) for line in (V01 / "pairs.jsonl").read_text(encoding="utf-8").splitlines()]
        predictions = {}
        for pair in v01_pairs:
            if pair["family"] != "transparent_granularity":
                continue
            licensed = next(item for item in pair["gold_edge_pairs"] if isinstance(item[1], list))
            predictions[pair["case_id"]] = {
                "case_id": pair["case_id"],
                "retrieval": {"candidate_rank": 1, "requires_structural_verification": True, "polarity_reliable": False},
                "verification": {
                    "predicted_class": "approximate",
                    "node_mapping": pair["gold_node_pairs"],
                    "edge_mapping": pair["gold_edge_pairs"],
                    "edge_path_matches": [{
                        "query_relation": licensed[0],
                        "candidate_relations": list(licensed[1]),
                        "realizes_nodes": ["x0"],
                    }],
                    "false_contractions": 0,
                },
            }
        overlay = runner.evaluate_v0_1_transparent_positives(predictions)
        self.assertEqual(overlay["transparent_cases"], 8)
        self.assertEqual(overlay["derived_false_contractions"], 0)
        self.assertEqual(overlay["status"], "pass")
        self.assertEqual(overlay["source"], "benchmark/r0-v0.1 (read-only)")


if __name__ == "__main__":
    unittest.main()
