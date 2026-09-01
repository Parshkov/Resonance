import ast
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.fingerprint.keys import FEATURE_VERSION, fingerprints
from src.graph import ThoughtGraph
from src.index import INDEX_VERSION, InvertedCandidateIndex
from src.interfaces import CandidateIndex, require_mode


EMPTY_SHA = hashlib.sha256(b"").hexdigest()
REPO = Path(__file__).parents[1]


def node(node_id: str, label: str, role: str, *, about=None, requires=None):
    record = {
        "id": node_id,
        "label": label,
        "role": role,
        "spans": [],
        "extract_conf": 1.0,
        "atomic": True,
        "assertion": "asserted",
        "modality": "actual",
    }
    if about or requires:
        record["knowledge"] = {
            "about": [{"id": item, "conf": 1.0, "via": "benchmark"} for item in (about or ())],
            "requires": [{"id": item, "conf": 1.0, "via": "benchmark"} for item in (requires or ())],
        }
    return record


def rel(rel_id: str, source: str, target: str, rel_type: str = "causes"):
    return {
        "id": rel_id,
        "source": source,
        "target": target,
        "type": rel_type,
        "extract_conf": 1.0,
        "spans": [],
        "assertion": "asserted",
        "modality": "actual",
    }


def graph(thought_id: str, labels: dict[str, str], edges: list[tuple[str, str, str, str]], *, knowledge=None):
    knowledge = knowledge or {}
    nodes = []
    roles = {
        "n0": "problem",
        "n1": "mechanism",
        "n2": "state",
        "n3": "outcome",
        "n4": "resource",
        "n5": "constraint",
        "n6": "resource",
        "n7": "resource",
        "c0": "problem",
        "c1": "mechanism",
        "c2": "state",
        "c3": "outcome",
    }
    for node_id, label in labels.items():
        extra = knowledge.get(node_id, {})
        nodes.append(node(node_id, label, roles[node_id], about=extra.get("about"), requires=extra.get("requires")))
    relations = [rel(rel_id, src, dst, typ) for rel_id, src, dst, typ in edges]
    return ThoughtGraph.from_dict(
        {
            "schema_version": "thought-dna/0.1",
            "thought_id": thought_id,
            "source": {"text": "", "sha256": EMPTY_SHA},
            "provenance": {"kind": "manual", "extractor": None, "human_id": "r3-test"},
            "nodes": nodes,
            "relations": relations,
        }
    )


CONSTELLATION_EDGES = [
    ("r0", "n0", "n1", "causes"),
    ("r1", "n1", "n2", "causes"),
    ("r2", "n2", "n3", "causes"),
    ("r3", "n4", "n1", "supports"),
    ("r4", "n5", "n1", "prevents"),
    ("r5", "n3", "n6", "causes"),
    ("r6", "n7", "n2", "supports"),
]


def battery(thought_id: str, prefix: str) -> ThoughtGraph:
    labels = {
        "n0": f"{prefix} problem",
        "n1": f"{prefix} mechanism",
        "n2": f"{prefix} heat",
        "n3": f"{prefix} failure",
        "n4": f"{prefix} load",
        "n5": f"{prefix} cooling",
        "n6": f"{prefix} loss",
        "n7": f"{prefix} current",
    }
    return graph(thought_id, labels, CONSTELLATION_EDGES)


def chain(thought_id: str) -> ThoughtGraph:
    return graph(
        thought_id,
        {"c0": "generic start", "c1": "generic process", "c2": "generic state", "c3": "generic end"},
        [
            ("c_r0", "c0", "c1", "causes"),
            ("c_r1", "c1", "c2", "causes"),
            ("c_r2", "c2", "c3", "causes"),
        ],
    )


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.query = battery("q-heat", "battery")
        self.analogue = battery("c-org", "organization")
        self.flip = graph(
            "c-flip",
            {
                "n0": "flip problem",
                "n1": "flip mechanism",
                "n2": "flip heat",
                "n3": "flip failure",
                "n4": "flip load",
                "n5": "flip cooling",
                "n6": "flip loss",
                "n7": "flip current",
            },
            [
                ("r0", "n0", "n1", "causes"),
                ("r1", "n1", "n2", "prevents"),
                ("r2", "n2", "n3", "causes"),
                ("r3", "n4", "n1", "supports"),
                ("r4", "n5", "n1", "prevents"),
                ("r5", "n3", "n6", "causes"),
                ("r6", "n7", "n2", "supports"),
            ],
        )
        self.chain = chain("c-chain")
        self.knowledge_hit = graph(
            "c-knowledge",
            {"n0": "other problem", "n1": "other method", "n2": "other state", "n3": "other outcome"},
            [("k0", "n0", "n1", "requires"), ("k1", "n1", "n3", "causes")],
            knowledge={"n0": {"about": ["local:thermo:heat"]}},
        )
        self.knowledge_query = graph(
            "q-knowledge",
            {"n0": "need heat model", "n1": "method", "n2": "state", "n3": "outcome"},
            [("q0", "n1", "n0", "requires"), ("q1", "n0", "n3", "causes")],
            knowledge={"n1": {"requires": ["local:thermo:heat"]}},
        )
        self.index = InvertedCandidateIndex(max_df_frac=1.0, min_df_cutoff=100)
        for item in (self.query, self.analogue, self.flip, self.chain, self.knowledge_hit):
            self.index.upsert(item)

    def test_index_satisfies_protocol(self):
        self.assertIsInstance(self.index, CandidateIndex)

    def test_default_query_is_multi_not_role_only(self):
        default = {key for key, _, _ in fingerprints(self.query)}
        multi = {key for key, _, _ in fingerprints(self.query, "MULTI")}
        d0 = {key for key, _, _ in fingerprints(self.query, "D0")}
        self.assertEqual(default, multi)
        self.assertGreater(len(multi), len(d0))
        hits = self.index.query(self.query, mode="analogical", k=10)
        self.assertTrue(hits)
        self.assertEqual(hits[0].feature_version, FEATURE_VERSION)
        self.assertIn("multi", hits[0].feature_version)

    def test_structural_keys_are_label_free(self):
        query_keys = {key for key, _, _ in fingerprints(self.query, "MULTI")}
        analogue_keys = {key for key, _, _ in fingerprints(self.analogue, "MULTI")}
        self.assertEqual(query_keys, analogue_keys)
        flip_keys = {key for key, _, _ in fingerprints(self.flip, "MULTI")}
        self.assertNotEqual(query_keys, flip_keys)

    def test_structural_channel_ranks_cross_domain_analogue_above_generic_chain(self):
        hits = {hit.candidate_id: hit for hit in self.index.query(self.query, mode="structural", k=10)}
        self.assertIn("c-org", hits)
        self.assertGreater(hits["c-org"].channel_scores["structural"], hits["c-chain"].channel_scores["structural"])
        self.assertTrue(hits["c-org"].seed_correspondences)
        self.assertTrue(all(seed.channel == "structural" for seed in hits["c-org"].seed_correspondences))

    def test_retrieval_is_polarity_unreliable_and_requires_verification(self):
        hits = self.index.query(self.query, mode="analogical", k=10)
        self.assertTrue(hits)
        for hit in hits:
            self.assertFalse(hit.polarity_reliable)
            self.assertTrue(hit.requires_structural_verification)
            self.assertEqual(hit.index_version, INDEX_VERSION)

    def test_channels_are_separate_and_mode_is_frozen(self):
        hits = self.index.query(self.knowledge_query, mode="complementary", k=10)
        by_id = {hit.candidate_id: hit for hit in hits}
        self.assertIn("c-knowledge", by_id)
        self.assertGreater(by_id["c-knowledge"].channel_scores["knowledge_complement"], 0.0)
        self.assertIn("content", by_id["c-knowledge"].channel_scores)
        self.assertIn("structural", by_id["c-knowledge"].channel_scores)
        with self.assertRaisesRegex(ValueError, "unsupported resonance mode"):
            self.index.query(self.query, mode="blend", k=5)
        require_mode("structural")

    def test_ablation_d0_is_not_the_shipping_path(self):
        ranked, _touched = self.index.query_ablation(self.query, variant="D0", k=10)
        self.assertTrue(ranked)
        self.assertNotIn("variant", InvertedCandidateIndex.query.__code__.co_varnames)

    def test_persistence_and_replay_are_deterministic(self):
        first = [hit.candidate_id for hit in self.index.query(self.query, mode="analogical", k=5)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "index.json"
            self.index.dump(path)
            restored = InvertedCandidateIndex.load(path)
        second = [hit.candidate_id for hit in restored.query(self.query, mode="analogical", k=5)]
        third = [hit.candidate_id for hit in self.index.query(self.query, mode="analogical", k=5)]
        self.assertEqual(first, second)
        self.assertEqual(first, third)
        self.assertEqual(restored.corpus_snapshot, self.index.corpus_snapshot)

    def test_fingerprint_and_index_do_not_import_verifier_or_mcp(self):
        forbidden = ("src.alignment", "src.scoring", "src.extraction", "src.mcp", "mcp")
        for folder in (REPO / "src" / "fingerprint", REPO / "src" / "index"):
            for path in folder.glob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        names = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        names = [node.module or ""]
                    else:
                        continue
                    for name in names:
                        self.assertFalse(any(name == item or name.startswith(item + ".") for item in forbidden), f"{path}: {name}")


if __name__ == "__main__":
    unittest.main()
