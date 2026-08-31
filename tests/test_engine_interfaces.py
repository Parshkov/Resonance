import ast
import hashlib
import json
import unittest
from pathlib import Path

from src.graph import ThoughtGraph
from src.interfaces import (
    SCORE_CONTRACT_VERSION,
    CandidateIndex,
    CandidateResult,
    ConfigRef,
    Contradiction,
    EdgePathMatch,
    EngineFacade,
    Explanation,
    ExtractionResult,
    Extractor,
    ItemProvenance,
    NodeMatch,
    RelationMatch,
    ResonanceHit,
    ScoreVector,
    SeedCorrespondence,
    StructuralVerifier,
    ThoughtStore,
    VerifierResult,
)

FIXTURE = Path(__file__).parent / "fixtures" / "thought_dna" / "valid_manual.json"


def graph_with_id(thought_id: str) -> ThoughtGraph:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["thought_id"] = thought_id
    return ThoughtGraph.from_dict(raw)


CFG = ConfigRef("fake", "0.1", hashlib.sha256(b"fake").hexdigest())


class FakeExtractor:
    def extract(self, context: str, *, source_id: str | None = None) -> ExtractionResult:
        return ExtractionResult(graph_with_id(source_id or "extracted"), CFG)


class FakeStore:
    def __init__(self):
        self.graphs = {}

    def put(self, graph: ThoughtGraph) -> None:
        self.graphs[graph.thought_id] = graph

    def get(self, thought_id: str) -> ThoughtGraph | None:
        return self.graphs.get(thought_id)

    def contains(self, thought_id: str) -> bool:
        return thought_id in self.graphs


class FakeIndex:
    def __init__(self):
        self.graphs = {}

    def upsert(self, graph: ThoughtGraph) -> None:
        self.graphs[graph.thought_id] = graph

    def remove(self, thought_id: str) -> None:
        self.graphs.pop(thought_id, None)

    def query(self, graph: ThoughtGraph, *, mode: str, k: int):
        out = []
        for rank, candidate_id in enumerate(sorted(self.graphs)):
            if candidate_id == graph.thought_id:
                continue
            out.append(CandidateResult(
                candidate_id=candidate_id,
                channel_scores={"content": 0.1, "structural": 0.8},
                channel_ranks={"content": rank + 1, "structural": rank + 1},
                seed_correspondences=(SeedCorrespondence("n1", "n1", 0.7, "structural"),),
                usable_query_evidence=1.0,
                requires_structural_verification=True,
                polarity_reliable=False,
                index_version="fake-index/0.1",
                feature_version="fake-feature/0.1",
                corpus_snapshot="fake-snapshot",
                config=CFG,
            ))
        return out[:k]


class FakeVerifier:
    def verify(self, query: ThoughtGraph, candidate: ThoughtGraph, *, seeds=()):
        qp = ItemProvenance(query.thought_id, "n1", query.provenance.kind, query.nodes[0].spans)
        cp = ItemProvenance(candidate.thought_id, "n1", candidate.provenance.kind, candidate.nodes[0].spans)
        mapping = (NodeMatch("n1", "n1", 1.0, qp, cp),)
        components = ScoreVector(
            structural=0.8,
            semantic=0.1,
            knowledge_about=0.0,
            knowledge_requires=0.0,
            complement_query_to_candidate=0.0,
            complement_candidate_to_query=0.0,
            coverage_containment=0.5,
            coverage_symmetric=0.5,
            contradiction=0.0,
            evidence_gate=0.5,
            retrieval_content=0.1,
            retrieval_structural=0.8,
        )
        explanation = Explanation(
            mapping=mapping,
            matched_relations=(),
            edge_path_matches=(),
            unmatched_query_nodes=("n2",),
            unmatched_candidate_nodes=("n2",),
            contradictions=(),
            retrieval_channels=("structural", "content"),
            systematicity_systems=(),
            score_model_version=SCORE_CONTRACT_VERSION,
            schema_version=query.schema_version,
            config_hash=CFG.config_hash,
        )
        return VerifierResult(
            contract_version=SCORE_CONTRACT_VERSION,
            query_id=query.thought_id,
            candidate_id=candidate.thought_id,
            candidate_config=CFG.config_hash,
            mapping=mapping,
            matched_relations=(),
            edge_path_matches=(),
            unmatched_query_nodes=("n2",),
            unmatched_candidate_nodes=("n2",),
            contradictions=(),
            hard_rejection=None,
            components=components,
            classification="analogical",
            confidence="provisional",
            explanation=explanation,
            solver_config=CFG,
        )


class FakeEngine:
    def __init__(self):
        self.extractor = FakeExtractor()
        self.store = FakeStore()
        self.indexer = FakeIndex()
        self.verifier = FakeVerifier()
        self.comparisons = {}

    def ingest(self, context: str, *, source_id: str | None = None) -> ThoughtGraph:
        graph = self.extractor.extract(context, source_id=source_id).graph
        self.store.put(graph)
        return graph

    def index(self, graph: ThoughtGraph) -> None:
        self.store.put(graph)
        self.indexer.upsert(graph)

    def find(self, graph: ThoughtGraph, *, mode: str, k: int = 20):
        hits = []
        for candidate in self.indexer.query(graph, mode=mode, k=k):
            target = self.store.get(candidate.candidate_id)
            verification = self.verifier.verify(graph, target, seeds=candidate.seed_correspondences)
            self.comparisons[(graph.thought_id, target.thought_id)] = verification
            hits.append(ResonanceHit(candidate, verification))
        return hits

    def compare(self, a: ThoughtGraph, b: ThoughtGraph, *, mode: str):
        result = self.verifier.verify(a, b)
        self.comparisons[(a.thought_id, b.thought_id)] = result
        return result

    def explain(self, a_id: str, b_id: str):
        return self.comparisons.get((a_id, b_id))

    def get(self, thought_id: str):
        return self.store.get(thought_id)


class InterfaceTests(unittest.TestCase):
    def test_fake_components_satisfy_protocols(self):
        self.assertIsInstance(FakeExtractor(), Extractor)
        self.assertIsInstance(FakeStore(), ThoughtStore)
        self.assertIsInstance(FakeIndex(), CandidateIndex)
        self.assertIsInstance(FakeVerifier(), StructuralVerifier)
        self.assertIsInstance(FakeEngine(), EngineFacade)

    def test_fake_end_to_end_flow_crosses_all_boundaries(self):
        engine = FakeEngine()
        query = engine.ingest("query", source_id="q")
        candidate = graph_with_id("c")
        engine.index(candidate)
        hits = engine.find(query, mode="analogical", k=20)
        self.assertEqual(len(hits), 1)
        hit = hits[0]
        self.assertEqual(hit.candidate.candidate_id, "c")
        self.assertFalse(hit.candidate.polarity_reliable)
        self.assertEqual(hit.verification.components.structural, 0.8)
        self.assertEqual(hit.verification.explanation.mapping[0].query_provenance.thought_id, "q")
        self.assertEqual(hit.verification.explanation.mapping[0].candidate_provenance.thought_id, "c")
        self.assertEqual(hit.verification.solver_config.config_hash, CFG.config_hash)
        self.assertIs(engine.explain("q", "c"), hit.verification)
        self.assertIs(engine.get("c"), candidate)

    def test_interface_package_has_no_downstream_or_transport_imports(self):
        root = Path(__file__).parents[1] / "src" / "interfaces"
        forbidden = ("src.extraction", "src.fingerprint", "src.index", "src.alignment", "src.scoring", "src.mcp", "mcp")
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [x.name for x in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                for name in names:
                    self.assertFalse(any(name == x or name.startswith(x + ".") for x in forbidden), f"{path}: forbidden import {name}")

    def test_score_contract_is_vector_not_blended_scalar(self):
        fields = ScoreVector.__dataclass_fields__
        for required in ("structural", "semantic", "knowledge_about", "knowledge_requires", "contradiction", "evidence_gate"):
            self.assertIn(required, fields)
        self.assertNotIn("score", fields)
        self.assertNotIn("similarity", fields)


if __name__ == "__main__":
    unittest.main()
