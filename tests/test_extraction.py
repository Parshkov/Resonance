import ast
import json
import unittest
from pathlib import Path

from src.extraction import (
    CueExtractor,
    ManualIngest,
    frozen_v0_1_coverage,
    frozen_v0_1_predictions,
    repeat_extraction_f1,
)
from src.graph import ThoughtDNAValidationError, ThoughtGraph
from src.interfaces import Extractor


REPO = Path(__file__).parents[1]
DEMO = "Heat accumulation causes degradation but cooling prevents failure."
IMPLICIT = "Heat builds up. Later the system fails."


class ExtractionTests(unittest.TestCase):
    def test_cue_extractor_satisfies_protocol(self):
        self.assertIsInstance(CueExtractor(), Extractor)

    def test_explicit_cues_are_span_grounded(self):
        result = CueExtractor().extract(DEMO, source_id="demo")
        graph = result.graph
        self.assertEqual(graph.provenance.kind, "extracted")
        self.assertEqual(graph.provenance.extractor["id"], "resonance-cue-extractor")
        self.assertEqual(graph.source.text, DEMO)
        types = {rel.type for rel in graph.relations}
        self.assertIn("causes", types)
        self.assertIn("prevents", types)
        for node in graph.nodes:
            self.assertTrue(node.spans)
            span = node.spans[0]
            self.assertEqual(DEMO[span.start:span.end], span.text)
            self.assertGreaterEqual(node.extract_conf, 0.35)
        for rel in graph.relations:
            self.assertTrue(rel.spans)
            self.assertIsNotNone(rel.cue)
            self.assertEqual(DEMO[rel.cue.start:rel.cue.end], rel.cue.text)

    def test_implicit_causation_is_abstained(self):
        result = CueExtractor().extract(IMPLICIT, source_id="implicit")
        self.assertFalse(result.graph.relations)
        self.assertTrue(any("implicit" in item for item in result.abstentions))

    def test_ungrounded_extracted_graph_is_rejected(self):
        raw = json.loads((REPO / "tests/fixtures/thought_dna/invalid_ungrounded_extracted.json").read_text(encoding="utf-8"))
        with self.assertRaises(ThoughtDNAValidationError):
            ThoughtGraph.from_dict(raw)

    def test_manual_bypass_uses_same_validator_without_llm(self):
        payload = json.loads((REPO / "tests/fixtures/thought_dna/valid_manual.json").read_text(encoding="utf-8"))
        graph = ManualIngest().ingest(payload)
        self.assertEqual(graph.provenance.kind, "manual")
        self.assertIsNone(graph.provenance.extractor)
        self.assertTrue(graph.nodes)

    def test_repeat_extraction_is_deterministic(self):
        extractor = CueExtractor()
        first = extractor.extract(DEMO, source_id="demo")
        second = extractor.extract(DEMO, source_id="demo")
        self.assertEqual(first.graph.to_dict(), second.graph.to_dict())
        scores = repeat_extraction_f1(first.graph, second.graph)
        self.assertEqual(scores["node_f1"], 1.0)
        self.assertEqual(scores["edge_f1"], 1.0)

    def test_repeat_edge_f1_aligns_endpoints_across_source_ids(self):
        extractor = CueExtractor()
        first = extractor.extract(DEMO, source_id="run-1")
        second = extractor.extract(DEMO, source_id="run-2")
        self.assertNotEqual(first.graph.thought_id, second.graph.thought_id)
        self.assertNotEqual({node.id for node in first.graph.nodes}, {node.id for node in second.graph.nodes})
        scores = repeat_extraction_f1(first.graph, second.graph)
        self.assertEqual(scores["node_f1"], 1.0)
        self.assertEqual(scores["edge_f1"], 1.0)
        self.assertGreaterEqual(len(first.graph.relations), 1)

    def test_overlap_merge_does_not_leave_dangling_relation_source(self):
        result = CueExtractor().extract("A caused by A B C strong heat causes D")
        ids = {node.id for node in result.graph.nodes}
        for rel in result.graph.relations:
            self.assertIn(rel.source, ids)
            self.assertIn(rel.target, ids)
        self.assertTrue(result.graph.relations)

    def test_no_doubt_does_not_invert_causal_polarity(self):
        result = CueExtractor().extract("No doubt, heat causes failure.")
        self.assertEqual(len(result.graph.relations), 1)
        rel = result.graph.relations[0]
        self.assertEqual(rel.type, "causes")
        self.assertEqual(rel.assertion, "asserted")

    def test_attached_verbal_negation_marks_negated(self):
        result = CueExtractor().extract("Cooling does not prevent failure.")
        self.assertEqual(len(result.graph.relations), 1)
        rel = result.graph.relations[0]
        self.assertEqual(rel.type, "prevents")
        self.assertEqual(rel.assertion, "negated")

    def test_drop_threshold_must_be_finite_unit_interval(self):
        CueExtractor(drop_threshold=0.0)
        CueExtractor(drop_threshold=1.0)
        for bad in (float("nan"), float("inf"), -1.0, 1.5, True):
            with self.assertRaises(ValueError):
                CueExtractor(drop_threshold=bad)

    def test_requires_emits_local_knowledge_without_network(self):
        result = CueExtractor().extract("The planner requires safety inventory.", source_id="k")
        self.assertTrue(any(rel.type == "requires" for rel in result.graph.relations))
        hooked = [node for node in result.graph.nodes if node.knowledge is not None]
        self.assertTrue(hooked)
        for node in hooked:
            refs = list(node.knowledge.about) + list(node.knowledge.requires)
            self.assertTrue(all(ref.id.startswith("local:") for ref in refs))
            self.assertTrue(all(ref.via == "extractor" for ref in refs))

    def test_frozen_v0_1_coverage_is_reported_and_not_vacuously_claimed(self):
        predictions = frozen_v0_1_predictions()
        self.assertEqual(len(predictions), 16)
        coverage = frozen_v0_1_coverage(predictions)
        self.assertEqual(coverage["n_records"], 16)
        self.assertEqual(coverage["total_nodes"], 0)
        self.assertEqual(coverage["total_relations"], 0)
        self.assertEqual(coverage["nonempty_graph_rate"], 0.0)
        for item in predictions:
            graph = item["thought_dna"]
            self.assertEqual(graph["provenance"]["kind"], "extracted")
            self.assertEqual(graph["nodes"], [])
            self.assertEqual(graph["relations"], [])
            ThoughtGraph.from_dict(graph)

    def test_extraction_package_does_not_import_downstream_or_network(self):
        forbidden = (
            "src.fingerprint", "src.index", "src.alignment", "src.scoring", "src.mcp",
            "mcp", "urllib", "requests", "http.client", "socket",
        )
        root = REPO / "src" / "extraction"
        for path in root.glob("*.py"):
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
