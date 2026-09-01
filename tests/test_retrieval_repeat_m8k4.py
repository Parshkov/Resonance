import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path

from src.fingerprint import FingerprintConfig, structural_fingerprints
from src.graph import ThoughtGraph
from src.index import CandidateRetrievalIndex, IndexConfig
from src.interfaces import CandidateIndex


ROOT = Path(__file__).parents[1]


def _manual_graph(
    thought_id,
    *,
    labels=("heat", "damage", "failure", "control"),
    relation_ids=("r0", "r1", "r2"),
    relations=None,
    about=None,
    requires=None,
):
    text = f"Manual graph {thought_id}."
    roles = ("problem", "mechanism", "outcome", "method")
    nodes = []
    for offset, (label, role) in enumerate(zip(labels, roles)):
        node = {
            "id": f"n{offset}",
            "label": label,
            "role": role,
            "spans": [],
            "extract_conf": 1.0,
            "atomic": True,
        }
        knowledge = {}
        if offset == 0 and about:
            knowledge["about"] = [{"id": about, "conf": 1.0, "via": "test"}]
        if offset == 0 and requires:
            knowledge["requires"] = [{"id": requires, "conf": 1.0, "via": "test"}]
        if knowledge:
            knowledge.setdefault("about", [])
            knowledge.setdefault("requires", [])
            node["knowledge"] = knowledge
        nodes.append(node)
    edges = relations or (
        ("n0", "n1", "causes"),
        ("n1", "n2", "causes"),
        ("n3", "n2", "prevents"),
    )
    return ThoughtGraph.from_dict(
        {
            "schema_version": "thought-dna/0.1",
            "thought_id": thought_id,
            "source": {
                "text": text,
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            },
            "provenance": {"kind": "manual", "extractor": None, "human_id": "test"},
            "nodes": nodes,
            "relations": [
                {
                    "id": relation_ids[offset],
                    "source": source,
                    "target": target,
                    "type": kind,
                    "extract_conf": 1.0,
                    "spans": [],
                }
                for offset, (source, target, kind) in enumerate(edges)
            ],
        }
    )


def _benchmark_graphs():
    rows = [
        json.loads(line)
        for line in (ROOT / "benchmark/r0-v0.1/graphs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return {
        row["benchmark_graph_id"]: ThoughtGraph.from_dict(row["thought_dna"])
        for row in rows
    }


def _integrity(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class FingerprintTests(unittest.TestCase):
    def test_shipping_policy_requires_multi_and_fixed_budget(self):
        policy = FingerprintConfig()
        self.assertEqual(policy.scales, ("D0", "D1"))
        self.assertEqual(policy.max_path_length, 3)
        self.assertEqual(policy.query_budget, 64)
        with self.assertRaisesRegex(ValueError, r"require D0\+D1"):
            FingerprintConfig(scales=("D0",))
        ablation = FingerprintConfig(scales=("D0",), allow_nonshipping_ablation=True)
        self.assertEqual(ablation.scales, ("D0",))

    def test_labels_and_serialized_ids_do_not_enter_structural_keys(self):
        left = _manual_graph("left")
        right = _manual_graph(
            "right",
            labels=("latency", "retry", "outage", "breaker"),
            relation_ids=("z9", "a0", "middle"),
        )
        left_features = [(x.key, x.scale, x.distance) for x in structural_fingerprints(left)]
        right_features = [(x.key, x.scale, x.distance) for x in structural_fingerprints(right)]
        self.assertEqual(left_features, right_features)

    def test_all_equal_paths_survive_relation_id_renaming(self):
        diamond = (
            ("n0", "n1", "causes"),
            ("n0", "n3", "causes"),
            ("n1", "n2", "causes"),
        )
        # Reuse the four-node helper but make a second equal path via n3.
        diamond = diamond + (("n3", "n2", "causes"),)
        first = _manual_graph("diamond-a", relation_ids=("r0", "r1", "r2", "r3"), relations=diamond)
        second = _manual_graph(
            "diamond-b",
            relation_ids=("zz", "aa", "mm", "bb"),
            relations=tuple(reversed(diamond)),
        )
        first_keys = sorted((x.key, x.scale, x.distance) for x in structural_fingerprints(first))
        second_keys = sorted((x.key, x.scale, x.distance) for x in structural_fingerprints(second))
        self.assertEqual(first_keys, second_keys)
        self.assertGreater(sum(1 for _, _, distance in first_keys if distance == 2), 2)


class CandidateIndexTests(unittest.TestCase):
    def test_index_satisfies_port_and_keeps_channel_evidence_separate(self):
        query = _manual_graph("query")
        analogue = _manual_graph("analogue", labels=("queue", "retry", "outage", "breaker"))
        lexical = _manual_graph(
            "lexical",
            relations=(("n0", "n2", "causes"), ("n2", "n1", "causes"), ("n3", "n1", "prevents")),
        )
        index = CandidateRetrievalIndex()
        self.assertIsInstance(index, CandidateIndex)
        index.extend((analogue, lexical))
        outcome = index.query_with_diagnostics(query, mode="analogical", k=10)
        by_id = {result.candidate_id: result for result in outcome.results}
        self.assertEqual(by_id["analogue"].channel_scores["structural"], 1.0)
        self.assertEqual(by_id["analogue"].channel_scores["content"], 0.0)
        self.assertGreater(by_id["lexical"].channel_scores["content"], 0.0)
        self.assertFalse(by_id["analogue"].polarity_reliable)
        self.assertTrue(by_id["analogue"].requires_structural_verification)
        self.assertTrue(by_id["analogue"].seed_correspondences)
        query_nodes = [seed.query_node for seed in by_id["analogue"].seed_correspondences]
        candidate_nodes = [seed.candidate_node for seed in by_id["analogue"].seed_correspondences]
        self.assertEqual(len(query_nodes), len(set(query_nodes)))
        self.assertEqual(len(candidate_nodes), len(set(candidate_nodes)))

    def test_query_budget_observability_and_deterministic_replay(self):
        graphs = _benchmark_graphs()
        index = CandidateRetrievalIndex(IndexConfig(enabled_channels=("structural",)))
        index.extend(graph for graph_id, graph in graphs.items() if graph_id.startswith("G") and not graph_id.endswith("-Q"))
        first = index.query_with_diagnostics(graphs["G01-Q"], mode="analogical", k=20)
        second = index.query_with_diagnostics(graphs["G01-Q"], mode="analogical", k=20)
        self.assertGreater(first.diagnostics.generated_structural_features, 64)
        self.assertEqual(first.diagnostics.selected_structural_features, 64)
        self.assertEqual(first.diagnostics.query_budget, 64)
        self.assertGreater(first.diagnostics.postings_touched_by_channel["structural"], 0)
        self.assertGreaterEqual(first.diagnostics.latency_ms_by_channel["structural"], 0.0)
        self.assertEqual(first.diagnostics.replay_sha256, second.diagnostics.replay_sha256)
        self.assertEqual(
            [(x.candidate_id, dict(x.channel_scores), x.seed_correspondences) for x in first.results],
            [(x.candidate_id, dict(x.channel_scores), x.seed_correspondences) for x in second.results],
        )

    def test_ties_use_min_rank_and_expose_cutoff_group(self):
        query = _manual_graph("query")
        index = CandidateRetrievalIndex(IndexConfig(enabled_channels=("structural",)))
        index.extend(
            _manual_graph(candidate_id, labels=(candidate_id, "x", "y", "z"))
            for candidate_id in ("a", "b", "c")
        )
        hard_cap = index.query_with_diagnostics(query, mode="analogical", k=2)
        self.assertEqual([result.candidate_id for result in hard_cap.results], ["a", "b"])
        self.assertEqual([result.channel_ranks["structural"] for result in hard_cap.results], [1, 1])
        self.assertEqual(hard_cap.diagnostics.tied_best_candidate_ids_by_channel["structural"], ("a", "b", "c"))
        self.assertEqual(hard_cap.diagnostics.cutoff_tied_candidate_ids, ("a", "b", "c"))
        self.assertTrue(hard_cap.diagnostics.cutoff_tie_truncated)

        tie_aware = index.query_with_diagnostics(
            query,
            mode="analogical",
            k=2,
            include_cutoff_ties=True,
        )
        self.assertEqual([result.candidate_id for result in tie_aware.results], ["a", "b", "c"])
        self.assertEqual(tie_aware.diagnostics.returned_candidate_count, 3)
        self.assertFalse(tie_aware.diagnostics.cutoff_tie_truncated)
        self.assertNotEqual(hard_cap.diagnostics.replay_sha256, tie_aware.diagnostics.replay_sha256)

    def test_content_channel_uses_postings_not_a_corpus_scan(self):
        index = CandidateRetrievalIndex(IndexConfig(enabled_channels=("content",)))
        for offset in range(100):
            index.upsert(
                _manual_graph(
                    f"candidate-{offset}",
                    labels=(f"unique{offset}", "other", "different", "control"),
                )
            )
        query = _manual_graph("query", labels=("unique42", "absentx", "absenty", "absentz"))
        outcome = index.query_with_diagnostics(query, mode="structural", k=10)
        self.assertEqual(outcome.results[0].candidate_id, "candidate-42")
        self.assertLess(outcome.diagnostics.postings_touched_by_channel["content"], 100)

    def test_directional_knowledge_complement_is_observable(self):
        query = _manual_graph("query", requires="local:test-concept")
        candidate = _manual_graph("candidate", about="local:test-concept")
        index = CandidateRetrievalIndex(IndexConfig(enabled_channels=("knowledge_complement",)))
        index.upsert(candidate)
        outcome = index.query_with_diagnostics(query, mode="complementary", k=3)
        self.assertEqual(len(outcome.results), 1)
        result = outcome.results[0]
        self.assertEqual(result.channel_scores["knowledge_complement"], 1.0)
        self.assertEqual(result.seed_correspondences[0].channel, "knowledge_complement")
        self.assertEqual(result.seed_correspondences[0].query_node, "n0")
        self.assertEqual(result.seed_correspondences[0].candidate_node, "n0")
        structural_mode = index.query_with_diagnostics(query, mode="structural", k=3)
        self.assertEqual(structural_mode.results, ())

    def test_persistence_round_trip_retains_df_policy_and_rejects_tampering(self):
        config = IndexConfig(max_df_ratio=0.73, max_df_floor=7)
        index = CandidateRetrievalIndex(config)
        index.extend((_manual_graph("a"), _manual_graph("b", labels=("x", "y", "z", "w"))))
        query = _manual_graph("query")
        before = index.query_with_diagnostics(query, mode="analogical", k=10)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.json"
            index.save(path)
            restored = CandidateRetrievalIndex.load(path, expected_config=config)
            after = restored.query_with_diagnostics(query, mode="analogical", k=10)
            self.assertEqual(restored.config.max_df_ratio, 0.73)
            self.assertEqual(restored.config.max_df_floor, 7)
            self.assertEqual(before.diagnostics.replay_sha256, after.diagnostics.replay_sha256)
            self.assertEqual(index.stats(), restored.stats())

            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["index_version"] = "forged-index-version"
            body = {key: value for key, value in payload.items() if key != "integrity_sha256"}
            payload["integrity_sha256"] = _integrity(body)
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "version metadata mismatch"):
                CandidateRetrievalIndex.load(path)

            index.save(path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["tie_policy_version"] = "forged-tie-policy"
            body = {key: value for key, value in payload.items() if key != "integrity_sha256"}
            payload["integrity_sha256"] = _integrity(body)
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "tie policy version metadata mismatch"):
                CandidateRetrievalIndex.load(path)

    def test_incremental_replace_and_remove_preserve_other_documents(self):
        index = CandidateRetrievalIndex(IndexConfig(enabled_channels=("structural",)))
        first = _manual_graph("first")
        second = _manual_graph("second")
        index.extend((first, second))
        original_postings = index.stats().structural_postings
        index.upsert(_manual_graph("second", labels=("new", "labels", "only", "changed")))
        self.assertEqual(index.stats().corpus_size, 2)
        self.assertEqual(index.stats().structural_postings, original_postings)
        index.remove("second")
        result = index.query(first, mode="structural", k=10)
        self.assertEqual(result, ())
        self.assertEqual(index.stats().corpus_size, 1)

    def test_remove_handles_repeated_keys_from_symmetric_endpoints(self):
        graph = _benchmark_graphs()["G01-Q"]
        features = structural_fingerprints(graph)
        self.assertLess(len({feature.key for feature in features}), len(features))
        index = CandidateRetrievalIndex(IndexConfig(enabled_channels=("structural",)))
        index.upsert(graph)
        index.remove(graph.thought_id)
        self.assertEqual(index.stats().corpus_size, 0)
        self.assertEqual(index.stats().structural_postings, 0)

    def test_invalid_policies_and_query_arguments_fail_closed(self):
        for value in (math.nan, math.inf, 0.0, 1.1):
            with self.assertRaises(ValueError):
                IndexConfig(max_df_ratio=value)
        with self.assertRaises(ValueError):
            IndexConfig(max_df_floor=True)
        index = CandidateRetrievalIndex()
        with self.assertRaises(ValueError):
            index.query(_manual_graph("query"), mode="analogical", k=0)


class FrozenBenchmarkEvidenceTests(unittest.TestCase):
    def test_structure_over_words_passes_but_cross_pack_gold_has_an_observational_collision(self):
        graphs = _benchmark_graphs()
        index = CandidateRetrievalIndex(IndexConfig(enabled_channels=("structural",)))
        index.extend(
            graph
            for graph_id, graph in graphs.items()
            if graph_id.startswith("G") and not graph_id.endswith("-Q")
        )
        sow = 0
        hard_cap_target_hits_at_20 = 0
        hard_cap_target_hits_at_5 = 0
        tie_aware_target_hits_at_20 = 0
        for offset in range(1, 7):
            pack = f"G{offset:02d}"
            outcome = index.query_with_diagnostics(graphs[f"{pack}-Q"], mode="analogical", k=96)
            ranks = {result.candidate_id: rank for rank, result in enumerate(outcome.results, 1)}
            scores = {result.candidate_id: result.channel_scores["structural"] for result in outcome.results}
            target = f"{pack}-C09"
            wrong_words = f"{pack}-C10"
            vocabulary = f"{pack}-C02"
            generic = f"{pack}-C13"
            sow += int(scores[vocabulary] > scores[wrong_words])
            sow += int(scores[target] > scores[wrong_words])
            hard_cap_target_hits_at_20 += int(ranks[target] <= 20)
            hard_cap_target_hits_at_5 += int(ranks[target] <= 5)
            self.assertGreater(scores[target], scores[generic])
            self.assertEqual(scores[target], 1.0)
            target_result = next(result for result in outcome.results if result.candidate_id == target)
            self.assertEqual(target_result.channel_ranks["structural"], 1)

            hard_cap = index.query_with_diagnostics(graphs[f"{pack}-Q"], mode="analogical", k=20)
            tie_aware = index.query_with_diagnostics(
                graphs[f"{pack}-Q"],
                mode="analogical",
                k=20,
                include_cutoff_ties=True,
            )
            tie_aware_target_hits_at_20 += int(
                target in {result.candidate_id for result in tie_aware.results}
            )
            self.assertTrue(hard_cap.diagnostics.cutoff_tie_truncated)
            self.assertEqual(len(hard_cap.diagnostics.cutoff_tied_candidate_ids), 48)
            self.assertFalse(tie_aware.diagnostics.cutoff_tie_truncated)
            self.assertEqual(len(tie_aware.results), 48)

        # All six gate packs compile to the same structural query. For each
        # query, 48 differently labelled candidates are structurally identical
        # under every allowed D0+D1 typed/directed feature. Gold selects one
        # pack-local C09, so structural-only tie-breaking cannot meet the gate
        # without reading forbidden semantic/benchmark identity information.
        first = index.query_with_diagnostics(graphs["G01-Q"], mode="analogical", k=96)
        perfect = [result for result in first.results if result.channel_scores["structural"] == 1.0]
        self.assertEqual(len(perfect), 48)
        self.assertEqual(sow, 12)
        self.assertEqual(hard_cap_target_hits_at_20, 2)
        self.assertEqual(hard_cap_target_hits_at_5, 0)
        self.assertEqual(tie_aware_target_hits_at_20, 6)


if __name__ == "__main__":
    unittest.main()
