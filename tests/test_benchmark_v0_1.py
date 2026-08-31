import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO = Path(__file__).parents[1]
BENCHMARK = REPO / "benchmark" / "r0-v0.1"


def load_runner():
    sys.path.insert(0, str(BENCHMARK))
    spec = importlib.util.spec_from_file_location("resonance_benchmark_runner", BENCHMARK / "runner.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


runner = load_runner()


def oracle_pair_predictions(bundle):
    records = []
    for pair in bundle.pairs:
        negative = pair["gold_class"] == "negative"
        polarity = pair["transform_manifest"].get("negative_subtype") == "polarity_flip"
        structural_score = 0.1 if negative else (0.2 if pair["gold_class"] == "complementary" else 0.9)
        retrieval = {
            "candidate_rank": 1,
            "channel_scores": {"content": 0.5, "knowledge": 0.2, "structural": structural_score},
            "requires_structural_verification": True,
            "polarity_reliable": False,
            "latency_seconds": 0.001,
            "postings_touched": 20,
        }
        verification = {
            "predicted_class": pair["gold_class"],
            "node_mapping": copy.deepcopy(pair["gold_node_pairs"]),
            "edge_mapping": copy.deepcopy(pair["gold_edge_pairs"]),
            "bridge_mapping": copy.deepcopy(pair["bridge_pairs"]),
            "hard_rejection": "causal polarity conflict" if polarity else None,
            "false_contractions": 0,
            "components": {"structural_score": structural_score, "H_sign_conflict": polarity},
            "latency_seconds": 0.01,
        }
        replay = {
            "candidate_rank": retrieval["candidate_rank"],
            "predicted_class": verification["predicted_class"],
            "node_mapping": copy.deepcopy(verification["node_mapping"]),
            "edge_mapping": copy.deepcopy(verification["edge_mapping"]),
            "bridge_mapping": copy.deepcopy(verification["bridge_mapping"]),
            "hard_rejection": verification["hard_rejection"],
            "components": copy.deepcopy(verification["components"]),
        }
        records.append({"case_id": pair["case_id"], "retrieval": retrieval, "verification": verification, "replay": replay})
    return records


def oracle_extraction_predictions(bundle):
    return [
        {
            "extraction_case_id": record["extraction_case_id"],
            "thought_dna": copy.deepcopy(record["reference_thought_dna"]),
        }
        for record in bundle.extraction_runs
    ]


def oracle_e1_predictions(bundle):
    records = []
    for case in bundle.e1_cases:
        records.append({
            "case_id": case["case_id"],
            "descriptor_results": {
                "D0": {"true_rank": 6, "true_score": 0.4, "best_generic_rank": 4, "best_generic_score": 0.5},
                "D1": {"true_rank": 3, "true_score": 0.7, "best_generic_rank": 5, "best_generic_score": 0.6},
                "MULTI": {"true_rank": 2, "true_score": 0.8, "best_generic_rank": 5, "best_generic_score": 0.6},
            },
            "polarity_flip_rank": 1,
            "polarity_flip_score": 0.9,
            "polarity_rejected_end_to_end": True,
            "polarity_reliable": False,
            "postings_touched": int(case["corpus_size"] ** 0.5),
            "build_seconds": 1.0,
            "query_seconds": 0.001,
            "live_keys": 100,
            "dead_keys": 10,
            "replay_hash": f"stable-{case['case_id']}",
            "rerun_hash": f"stable-{case['case_id']}",
        })
    return records


def oracle_scale_predictions():
    records = []
    for world in ("rich_random", "zipf_chains"):
        for size, touched in ((1_000, 100), (10_000, 300), (100_000, 900)):
            case_id = f"S-{world}-{size}"
            records.append({
                "case_id": case_id,
                "world": world,
                "corpus_size": size,
                "seed": 1729,
                "synthetic": True,
                "feature_distribution": world,
                "build_seconds": size / 10_000,
                "index_bytes": size * 100,
                "posting_length": {"median": 2, "p95": 20, "maximum": 100},
                "postings_touched": touched,
                "query_latency_seconds": {"p50": 0.001, "p95": 0.002},
                "recall_at_5": 0.75,
                "recall_at_20": 0.8,
                "peak_memory_bytes": size * 200,
                "replay_hash": f"stable-{case_id}",
                "rerun_hash": f"stable-{case_id}",
            })
    return records


class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = runner.validate_fixtures()

    def test_counts_splits_families_and_thought_dna(self):
        self.assertEqual(len(self.bundle.graphs), 136)
        self.assertEqual(len(self.bundle.pairs), 128)
        self.assertEqual(len(self.bundle.extraction_runs), 16)
        self.assertEqual(len(self.bundle.e1_cases), 12)
        packs = {}
        for pair in self.bundle.pairs:
            packs.setdefault(pair["pack_id"], set()).add(pair["family"])
        self.assertEqual(set(packs), {"C01", "C02", "G01", "G02", "G03", "G04", "G05", "G06"})
        self.assertTrue(all(len(families) == 16 for families in packs.values()))
        self.assertEqual(sum(pair["split"] == "calibration" for pair in self.bundle.pairs), 32)
        self.assertEqual(sum(pair["split"] == "gate" for pair in self.bundle.pairs), 96)

    def test_gold_is_not_in_graph_engine_inputs(self):
        forbidden = {"gold_class", "gold_node_pairs", "gold_edge_pairs", "relevant", "rationale", "review", "family"}
        for wrapper in self.bundle.graphs:
            self.assertEqual(set(wrapper), {"benchmark_graph_id", "thought_dna"})
            serialized = json.dumps(wrapper["thought_dna"], sort_keys=True)
            self.assertTrue(all(f'"{field}"' not in serialized for field in forbidden))
        self.assertFalse(self.bundle.summary["engine_input_projection"]["gold_in_engine_input"])

    def test_manual_judgments_are_independently_approved_not_self_approved(self):
        required_pairs = [pair for pair in self.bundle.pairs if pair["review"]["required"]]
        reviewer = "parshkov-xai-grok46-k3e8"
        author = "parshkov-openai-gpt5-codex-s7d3"
        self.assertEqual(len(required_pairs), 64)
        self.assertTrue(all(pair["review"]["status"] == "approved" for pair in required_pairs))
        self.assertTrue(all(pair["review"]["reviewer"] == reviewer for pair in required_pairs))
        self.assertTrue(all(record["review"]["status"] == "approved" for record in self.bundle.extraction_runs))
        self.assertTrue(all(record["review"]["reviewer"] == reviewer for record in self.bundle.extraction_runs))
        self.assertNotEqual(reviewer, author)
        self.assertEqual(self.bundle.summary["manual_pair_reviews_unapproved"], 0)
        self.assertEqual(self.bundle.summary["extraction_reviews_unapproved"], 0)
        self.assertTrue(self.bundle.summary["gate_execution_ready"])
        self.assertEqual(self.bundle.manifest["freeze_state"], "independent_review_complete")

    def test_vocabulary_substitution_is_not_a_copy_of_the_analogy_graph(self):
        by_pack = {}
        for pair in self.bundle.pairs:
            by_pack.setdefault(pair["pack_id"], {})[pair["family"]] = pair
        graphs = {wrapper["benchmark_graph_id"]: wrapper["thought_dna"] for wrapper in self.bundle.graphs}
        for pack, families in by_pack.items():
            vocab = graphs[families["vocabulary_substitution"]["candidate_graph"]]
            analog = graphs[families["cross_domain_analogy"]["candidate_graph"]]
            query = graphs[families["paraphrase"]["query_graph"]]
            vocab_labels = [node["label"] for node in vocab["nodes"] if node["id"].startswith("n")]
            analog_labels = [node["label"] for node in analog["nodes"] if node["id"].startswith("n")]
            query_labels = [node["label"] for node in query["nodes"] if node["id"].startswith("n")]
            self.assertNotEqual(vocab_labels, analog_labels, pack)
            self.assertNotEqual(vocab_labels, query_labels, pack)
            analog_rel = [(rel["source"], rel["type"], rel["target"]) for rel in analog["relations"]]
            vocab_rel = [(rel["source"], rel["type"], rel["target"]) for rel in vocab["relations"]]
            self.assertEqual(vocab_rel, analog_rel, pack)

    def test_gate_family_10_has_required_anti_invariance_allocation(self):
        cases = [
            pair for pair in self.bundle.pairs
            if pair["split"] == "gate" and pair["family"] == "same_vocabulary_wrong_structure"
        ]
        subtypes = [pair["transform_manifest"]["negative_subtype"] for pair in cases]
        self.assertEqual(subtypes.count("polarity_flip"), 2)
        self.assertEqual(subtypes.count("direction_reversal"), 2)
        self.assertEqual(subtypes.count("broader_rewire"), 2)

    def test_e1_matrix_is_two_world_dna_native_and_complete(self):
        self.assertEqual({case["world"] for case in self.bundle.e1_cases}, {"rich_random", "zipf_chains"})
        self.assertTrue(all(case["descriptors"] == ["D0", "D1", "MULTI"] for case in self.bundle.e1_cases))
        expected_relations = {"causes", "prevents", "requires", "part_of", "constrains", "supports", "contradicts"}
        self.assertTrue(all(set(case["relation_vocabulary"]) == expected_relations for case in self.bundle.e1_cases))
        for world in ("rich_random", "zipf_chains"):
            world_cases = [case for case in self.bundle.e1_cases if case["world"] == world]
            self.assertEqual(len(world_cases), 6)
            self.assertEqual({case["seed"] for case in world_cases}, {1729, 7, 17, 31})

    def test_all_relative_schema_references_resolve(self):
        for schema_path in (BENCHMARK / "schema").glob("*.json"):
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            pending = [schema]
            while pending:
                value = pending.pop()
                if isinstance(value, dict):
                    reference = value.get("$ref")
                    if reference and not reference.startswith("#"):
                        path_part = reference.split("#", 1)[0]
                        self.assertTrue((schema_path.parent / path_part).resolve().is_file(), reference)
                    pending.extend(value.values())
                elif isinstance(value, list):
                    pending.extend(value)

    def test_cli_validation_is_deterministic(self):
        command = [sys.executable, str(BENCHMARK / "runner.py"), "validate"]
        first = subprocess.run(command, cwd=REPO, check=True, capture_output=True, text=True).stdout
        second = subprocess.run(command, cwd=REPO, check=True, capture_output=True, text=True).stdout
        self.assertEqual(first, second)
        self.assertEqual(json.loads(first)["manifest_sha256"], self.bundle.manifest_sha256)


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.bundle = runner.validate_fixtures()
        self.pairs = oracle_pair_predictions(self.bundle)
        self.extraction = oracle_extraction_predictions(self.bundle)
        self.e1 = oracle_e1_predictions(self.bundle)
        self.scale = oracle_scale_predictions()

    def test_oracle_adapter_passes_measured_engine_gates_and_independent_gold_review(self):
        report = runner.evaluate(self.bundle, self.pairs, self.extraction, self.e1, self.scale)
        for gate in (
            "sow", "overall_recall_at_5", "positive_family_recall", "resonance_precision",
            "overall_negative_fpr", "negative_family_fpr", "node_pair_f1",
            "directed_typed_edge_accuracy", "false_meaningful_contractions",
            "deterministic_replay", "verifier_p95_seconds", "polarity_rejection",
            "extraction_prerequisite", "structural_e1_matrix", "structural_scale_replay",
            "independent_gold_review",
        ):
            self.assertEqual(report["gates"][gate]["status"], "pass", gate)
        self.assertEqual(report["overall_status"], "pass")

    def test_report_replay_is_byte_deterministic(self):
        first = runner.evaluate(self.bundle, self.pairs, self.extraction, self.e1, self.scale)
        second = runner.evaluate(
            self.bundle,
            list(reversed(copy.deepcopy(self.pairs))),
            list(reversed(copy.deepcopy(self.extraction))),
            list(reversed(copy.deepcopy(self.e1))),
            list(reversed(copy.deepcopy(self.scale))),
        )
        self.assertEqual(runner.canonical_bytes(first), runner.canonical_bytes(second))
        expected_hash = first.pop("report_sha256")
        self.assertEqual(expected_hash, runner.canonical_sha256(first))

    def test_pipeline_attribution_separates_retrieval_and_polarity_verifier_failures(self):
        by_id = {record["case_id"]: record for record in self.pairs}
        missed = by_id["G01-09"]
        missed["retrieval"]["candidate_rank"] = 99
        missed["replay"]["candidate_rank"] = 99
        polarity = by_id["G01-10"]
        polarity["verification"]["predicted_class"] = "direct"
        polarity["verification"]["hard_rejection"] = None
        polarity["replay"]["predicted_class"] = "direct"
        polarity["replay"]["hard_rejection"] = None
        report = runner.evaluate(self.bundle, list(by_id.values()), self.extraction, self.e1, self.scale)
        self.assertGreaterEqual(report["pipeline_attribution"]["retrieval_miss"], 1)
        self.assertGreaterEqual(report["pipeline_attribution"]["polarity_rejection_failure"], 1)
        self.assertEqual(report["gates"]["polarity_rejection"]["status"], "fail")
        self.assertLess(report["metrics"]["overall_gate_recall_at_5"], 1.0)

    def test_structural_retrieval_flags_fail_closed(self):
        self.pairs[0]["retrieval"]["polarity_reliable"] = True
        with self.assertRaisesRegex(runner.BenchmarkError, "polarity-unreliable"):
            runner.evaluate(self.bundle, self.pairs, self.extraction, self.e1, self.scale)

    def test_e1_and_scale_failures_are_non_compensating_and_attributed(self):
        self.e1[0]["descriptor_results"]["MULTI"]["true_score"] = 0.5
        self.e1[0]["descriptor_results"]["MULTI"]["best_generic_score"] = 0.6
        self.scale[-1]["postings_touched"] = 9_000
        report = runner.evaluate(self.bundle, self.pairs, self.extraction, self.e1, self.scale)
        self.assertEqual(report["gates"]["structural_e1_matrix"]["status"], "fail")
        self.assertEqual(report["gates"]["structural_scale_replay"]["status"], "fail")
        self.assertEqual(report["overall_status"], "fail")


if __name__ == "__main__":
    unittest.main()
