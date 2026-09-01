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
from src.engine import EngineIntegrityError, InMemoryThoughtStore, ResonanceEngine

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
    def _engine(self, count=20):
        engine = ResonanceEngine()
        subset = list(GRAPHS.values())[:count]
        for g in subset:
            engine.index(g)
        return engine, subset

    def test_bound_snapshot_round_trip_preserves_find(self):
        engine, subset = self._engine()
        query = subset[0]
        before = [(h.candidate.candidate_id, h.verification.classification)
                  for h in engine.find(query, mode="structural", k=5)]
        with tempfile.TemporaryDirectory() as tmp:
            engine.dump(Path(tmp))
            restored = ResonanceEngine.load(Path(tmp))
        after = [(h.candidate.candidate_id, h.verification.classification)
                 for h in restored.find(query, mode="structural", k=5)]
        self.assertEqual(before, after)

    def test_mixed_store_index_pair_is_rejected_on_load(self):
        """A 1-graph store bound to a 20-graph index must fail closed."""
        big, subset = self._engine(20)
        small, _ = self._engine(1)
        with tempfile.TemporaryDirectory() as tmp:
            big.dump(Path(tmp))
            small.store.dump(Path(tmp) / "store.json")   # swap in mismatched store
            import hashlib, json
            mpath = Path(tmp) / "manifest.json"
            manifest = json.loads(mpath.read_text())
            manifest["files"]["store.json"] = hashlib.sha256(
                (Path(tmp) / "store.json").read_bytes()).hexdigest()
            mpath.write_text(json.dumps(manifest, sort_keys=True,
                                        separators=(",", ":")) + "\n")
            with self.assertRaises(EngineIntegrityError):
                ResonanceEngine.load(Path(tmp))

    def test_tampered_snapshot_file_is_rejected(self):
        engine, _ = self._engine(5)
        with tempfile.TemporaryDirectory() as tmp:
            engine.dump(Path(tmp))
            index_path = Path(tmp) / "index.json"
            index_path.write_bytes(index_path.read_bytes().replace(b"causes", b"caused", 1))
            with self.assertRaises(EngineIntegrityError):
                ResonanceEngine.load(Path(tmp))

    def test_find_fails_closed_when_store_misses_a_candidate(self):
        """A retrieved candidate absent from the store raises; it is never
        silently skipped (reviewer finding 1 regression)."""
        engine, subset = self._engine(5)
        engine.store._graphs.pop(subset[1].thought_id)   # simulate divergence
        with self.assertRaises(EngineIntegrityError):
            # query with a SIBLING so the popped graph is retrieved as a
            # candidate (the index excludes the query's own id)
            engine.find(subset[0], mode="structural", k=5)


if __name__ == "__main__":
    unittest.main()
