"""R5 integration tests: the composed engine over frozen v0.1 fixtures.

Covers the mission's required demos -- lexical hard negative, cross-domain
analogy, partial/granularity, polarity/causal contradiction, complementarity
-- plus facade protocol conformance, persistence composition, and the
MCP-absence guarantee.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.graph import ThoughtGraph
from src.interfaces import EngineFacade, ThoughtStore
from src.engine import ENGINE_VERSION, InMemoryThoughtStore, ResonanceEngine
from src.index.store import InvertedCandidateIndex

V01 = REPO / "benchmark" / "r0-v0.1"


def load_fixtures():
    graphs = {}
    for line in (V01 / "graphs.jsonl").read_text().splitlines():
        d = json.loads(line)
        graphs[d["benchmark_graph_id"]] = ThoughtGraph.from_dict(d["thought_dna"])
    pairs = [json.loads(line) for line in (V01 / "pairs.jsonl").read_text().splitlines()]
    return graphs, pairs


GRAPHS, PAIRS = load_fixtures()


def pair_of(family):
    return next(p for p in PAIRS if p["family"] == family)


class FacadeTests(unittest.TestCase):
    def test_engine_satisfies_facade_and_store_protocols(self):
        engine = ResonanceEngine()
        self.assertIsInstance(engine, EngineFacade)
        self.assertIsInstance(engine.store, ThoughtStore)

    def test_engine_never_imports_mcp(self):
        """The guarantee is import-independence, not MCP's absence from the
        repo -- after R6 lands a transport package this must keep passing."""
        engine = ResonanceEngine()
        g = engine.ingest("Heat causes failure.", source_id="mcp-free")
        engine.index(g)
        engine.find(g, mode="structural", k=3)
        self.assertTrue(engine.get(g.thought_id) is g)
        loaded = [name for name in sys.modules if name == "src.mcp"
                  or name.startswith("src.mcp.")]
        self.assertEqual(loaded, [], "engine pulled in MCP transport modules")

    def test_manual_bypass_reaches_the_same_interfaces(self):
        engine = ResonanceEngine()
        pair = PAIRS[0]                                   # paraphrase pair, both manual
        manual = GRAPHS[pair["candidate_graph"]]
        self.assertEqual(manual.provenance.kind, "manual")
        engine.index(manual)
        hits = engine.find(GRAPHS[pair["query_graph"]], mode="structural", k=5)
        self.assertTrue(any(h.candidate.candidate_id == manual.thought_id for h in hits))
        self.assertEqual(hits[0].verification.classification, "direct")


class RequiredDemoTests(unittest.TestCase):
    """The five acceptance demos, each on frozen benchmark fixtures."""

    @classmethod
    def setUpClass(cls):
        cls.engine = ResonanceEngine()
        for graph in GRAPHS.values():
            cls.engine.index(graph)

    def _verify(self, pair, mode):
        return self.engine.compare(GRAPHS[pair["query_graph"]],
                                   GRAPHS[pair["candidate_graph"]], mode=mode)

    def test_demo_lexical_hard_negative(self):
        r = self._verify(pair_of("same_vocabulary_wrong_structure"), "structural")
        self.assertEqual(r.classification, "negative")
        self.assertGreater(r.components.semantic, 0.9)   # same words...
        self.assertLess(r.components.structural, 0.85)   # ...wrong structure

    def test_demo_cross_domain_analogy(self):
        pair = pair_of("cross_domain_analogy")
        r = self._verify(pair, "analogical")
        self.assertEqual(r.classification, "analogical")
        self.assertLess(r.components.semantic, 0.3)
        self.assertGreaterEqual(r.components.structural, 0.85)
        # and end-to-end: the analogue is in the engine's tied-best group
        hits = self.engine.find(GRAPHS[pair["query_graph"]], mode="analogical", k=20)
        ids = {h.candidate.candidate_id for h in hits}
        self.assertIn(pair["candidate_graph"], ids)

    def test_demo_partial_and_granularity(self):
        r = self._verify(pair_of("partial_graph"), "structural")
        self.assertEqual(r.classification, "approximate")
        self.assertGreater(r.components.coverage_containment,
                           r.components.coverage_symmetric)
        r2 = self._verify(pair_of("transparent_granularity"), "structural")
        self.assertEqual(r2.classification, "approximate")
        self.assertGreater(r2.components.r_path, 0.0)     # guarded path credit

    def test_demo_polarity_contradiction(self):
        pair = next(p for p in PAIRS
                    if p["transform_manifest"].get("negative_subtype") == "polarity_flip")
        r = self._verify(pair, "structural")
        self.assertIsNotNone(r.hard_rejection)
        self.assertTrue(r.components.h_sign_conflict)
        self.assertEqual(r.components.structural, 0.0)
        self.assertEqual(r.classification, "negative")

    def test_demo_complementarity(self):
        r = self._verify(pair_of("method_knowledge_bridge"), "complementary")
        self.assertEqual(r.classification, "complementary")
        self.assertGreater(max(r.components.complement_query_to_candidate,
                               r.components.complement_candidate_to_query), 0.0)


class PersistenceCompositionTests(unittest.TestCase):
    def test_bound_snapshot_round_trip_preserves_find(self):
        engine = ResonanceEngine()
        subset = list(GRAPHS.values())[:8]
        for g in subset:
            engine.index(g)
        query = subset[0]
        before = [(h.candidate.candidate_id, h.verification.classification)
                  for h in engine.find(query, mode="structural", k=5)]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "engine"
            engine.dump(root)
            restored = ResonanceEngine.load(root)
        after = [(h.candidate.candidate_id, h.verification.classification)
                 for h in restored.find(query, mode="structural", k=5)]
        self.assertEqual(before, after)
        self.assertEqual(restored.manifest()["engine_version"], ENGINE_VERSION)
        self.assertEqual(restored.manifest()["corpus_snapshot"],
                         engine.candidate_index.corpus_snapshot)

    def test_mixed_store_and_index_are_rejected(self):
        store = InMemoryThoughtStore()
        store.put(list(GRAPHS.values())[0])
        index = InvertedCandidateIndex()
        index.build(list(GRAPHS.values())[1:4])
        with self.assertRaisesRegex(ValueError, "snapshots diverge"):
            ResonanceEngine(store=store, index=index)

    def test_find_fails_closed_if_index_candidate_missing_from_store(self):
        engine = ResonanceEngine()
        subset = [GRAPHS[key] for key in sorted(GRAPHS) if key.startswith("C01-")]
        for g in subset:
            engine.index(g)
        query = GRAPHS["C01-Q"]
        hits = engine.find(query, mode="structural", k=5)
        self.assertTrue(hits)
        engine.store._graphs.pop(hits[0].candidate.candidate_id)
        with self.assertRaisesRegex(ValueError, "snapshots diverge|absent from the bound store"):
            engine.find(query, mode="structural", k=5)

    def test_tampered_manifest_version_is_rejected(self):
        engine = ResonanceEngine()
        engine.index(list(GRAPHS.values())[0])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "engine"
            engine.dump(root)
            payload = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            payload["engine_version"] = "tampered-engine"
            (root / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "engine_version"):
                ResonanceEngine.load(root)


if __name__ == "__main__":
    unittest.main()
