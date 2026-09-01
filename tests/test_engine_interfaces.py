import ast
import hashlib
import json
import math
import sys
import unittest
from pathlib import Path

from src.graph import ThoughtGraph
from src.interfaces import (
    MINIMUM_PYTHON,
    REQUIRED_SCORE_WIRE_NAMES,
    RESONANCE_MODES,
    SCORE_CONTRACT_VERSION,
    SCORE_WIRE_NAMES,
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
    RetrievalFlags,
    ScoreVector,
    SeedCorrespondence,
    StructuralVerifier,
    ThoughtStore,
    VerifierResult,
    require_mode,
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
        require_mode(mode)
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


def _empty_explanation_kwargs(query: ThoughtGraph, mapping=(), matched_relations=(), edge_path_matches=(), contradictions=()):
    return {
        "mapping": mapping,
        "matched_relations": matched_relations,
        "edge_path_matches": edge_path_matches,
        "unmatched_query_nodes": ("n2",),
        "unmatched_candidate_nodes": ("n2",),
        "unmatched_query_relations": ("r9",),
        "unmatched_candidate_relations": ("r9",),
        "contradictions": contradictions,
        "retrieval_channels": ("structural", "content"),
        "systematicity_systems": (),
        "score_model_version": SCORE_CONTRACT_VERSION,
        "schema_version": query.schema_version,
        "config_hash": CFG.config_hash,
    }


class FakeVerifier:
    def verify(self, query: ThoughtGraph, candidate: ThoughtGraph, *, seeds=()):
        qp = ItemProvenance(query.thought_id, "n1", query.provenance.kind, query.nodes[0].spans)
        cp = ItemProvenance(candidate.thought_id, "n1", candidate.provenance.kind, candidate.nodes[0].spans)
        mapping = (NodeMatch("n1", "n1", 1.0, qp, cp),)
        qrp = ItemProvenance(query.thought_id, "r0", query.provenance.kind, ())
        crp = ItemProvenance(candidate.thought_id, "r0a", candidate.provenance.kind, ())
        xnp = ItemProvenance(candidate.thought_id, "x0", candidate.provenance.kind, ())
        paths = (
            EdgePathMatch("r0", ("r0a",), ("x0",), 1.0, qrp, (crp,), (xnp,)),
        )
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
            n_role=0.1,
            r_direct=0.7,
            r_direct_unweighted=0.65,
            r_path=0.1,
            y_systematicity=0.8,
            h_sign_conflict=False,
            e_nodes=2.0,
            e_relations=1.0,
            knowledge_evidence_present=False,
            rarity_weighting=False,
            retrieval_content=0.1,
            retrieval_structural=0.8,
        )
        shared = _empty_explanation_kwargs(query, mapping=mapping, edge_path_matches=paths)
        explanation = Explanation(**shared)
        flags = RetrievalFlags(requires_structural_verification=True, polarity_reliable=False)
        return VerifierResult(
            contract_version=SCORE_CONTRACT_VERSION,
            query_id=query.thought_id,
            candidate_id=candidate.thought_id,
            candidate_config=CFG.config_hash,
            mapping=mapping,
            matched_relations=(),
            edge_path_matches=paths,
            unmatched_query_nodes=shared["unmatched_query_nodes"],
            unmatched_candidate_nodes=shared["unmatched_candidate_nodes"],
            unmatched_query_relations=shared["unmatched_query_relations"],
            unmatched_candidate_relations=shared["unmatched_candidate_relations"],
            contradictions=(),
            hard_rejection=None,
            components=components,
            classification="analogical",
            confidence="provisional",
            explanation=explanation,
            solver_config=CFG,
            retrieval_flags=flags,
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
        require_mode(mode)
        hits = []
        for candidate in self.indexer.query(graph, mode=mode, k=k):
            target = self.store.get(candidate.candidate_id)
            verification = self.verifier.verify(graph, target, seeds=candidate.seed_correspondences)
            self.comparisons[(graph.thought_id, target.thought_id)] = verification
            hits.append(ResonanceHit(candidate, verification))
        return hits

    def compare(self, a: ThoughtGraph, b: ThoughtGraph, *, mode: str):
        require_mode(mode)
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
        self.assertEqual(hit.verification.unmatched_query_relations, ("r9",))
        self.assertEqual(hit.verification.unmatched_candidate_relations, ("r9",))
        self.assertEqual(hit.verification.retrieval_flags.to_wire(), {
            "requires_structural_verification": True,
            "polarity_reliable": False,
        })
        self.assertEqual(hit.verification.explanation.unmatched_query_relations, ("r9",))
        self.assertEqual(hit.verification.edge_path_matches[0].candidate_provenances[0].item_id, "r0a")
        self.assertEqual(hit.verification.edge_path_matches[0].realizes_node_provenances[0].item_id, "x0")
        self.assertEqual(hit.verification.components.r_direct_unweighted, 0.65)
        self.assertFalse(hit.verification.components.knowledge_evidence_present)
        self.assertFalse(hit.verification.components.rarity_weighting)
        self.assertEqual(hit.candidate.candidate_id, hit.verification.candidate_id)
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
        for required in (
            "structural", "semantic", "knowledge_about", "knowledge_requires", "contradiction",
            "evidence_gate", "n_role", "r_direct", "r_direct_unweighted", "r_path", "y_systematicity",
            "h_sign_conflict", "e_nodes", "e_relations", "knowledge_evidence_present", "rarity_weighting",
        ):
            self.assertIn(required, fields)
        self.assertNotIn("score", fields)
        self.assertNotIn("similarity", fields)

    def test_score_vector_round_trips_scoring_v0_1_wire_names(self):
        vector = ScoreVector(
            structural=0.8,
            semantic=0.1,
            knowledge_about=0.2,
            knowledge_requires=0.0,
            complement_query_to_candidate=0.3,
            complement_candidate_to_query=0.0,
            coverage_containment=0.5,
            coverage_symmetric=0.4,
            contradiction=0.01,
            evidence_gate=0.9,
            n_role=0.1,
            r_direct=0.7,
            r_direct_unweighted=0.6,
            r_path=0.05,
            y_systematicity=0.8,
            h_sign_conflict=True,
            e_nodes=5.0,
            e_relations=4.0,
            knowledge_evidence_present=True,
            rarity_weighting=True,
            retrieval_content=0.2,
            retrieval_knowledge=0.0,
            retrieval_structural=0.7,
            extras={"debug_margin": 0.01},
        )
        wire = vector.to_wire()
        self.assertEqual(set(SCORE_WIRE_NAMES.values()), REQUIRED_SCORE_WIRE_NAMES)
        for python_name, wire_name in SCORE_WIRE_NAMES.items():
            self.assertIn(wire_name, wire)
            self.assertEqual(wire[wire_name], getattr(vector, python_name))
        self.assertEqual(wire["extras"], {"debug_margin": 0.01})
        restored = ScoreVector.from_wire(wire)
        self.assertEqual(restored.to_wire(), wire)
        self.assertTrue(restored.h_sign_conflict)
        self.assertTrue(restored.knowledge_evidence_present)
        self.assertTrue(restored.rarity_weighting)
        self.assertEqual(restored.r_direct_unweighted, 0.6)
        self.assertEqual(restored.q_containment, 0.5)
        self.assertEqual(restored.x_contradiction, 0.01)

    def test_candidate_maps_are_snapshotted_against_alias_mutation(self):
        scores = {"content": 0.1, "structural": 0.8}
        ranks = {"content": 1, "structural": 1}
        candidate = CandidateResult(
            candidate_id="c",
            channel_scores=scores,
            channel_ranks=ranks,
            seed_correspondences=(),
            usable_query_evidence=1.0,
            requires_structural_verification=True,
            polarity_reliable=False,
            index_version="i",
            feature_version="f",
            corpus_snapshot="s",
            config=CFG,
        )
        scores["content"] = 99.0
        ranks["structural"] = 99
        self.assertEqual(candidate.channel_scores["content"], 0.1)
        self.assertEqual(candidate.channel_ranks["structural"], 1)
        with self.assertRaises(TypeError):
            candidate.channel_scores["content"] = 0.0

    def test_verifier_rejects_contradictory_explanation_payload(self):
        query = graph_with_id("q")
        candidate = graph_with_id("c")
        result = FakeVerifier().verify(query, candidate)
        with self.assertRaisesRegex(ValueError, "unmatched_query_nodes"):
            VerifierResult(
                **{
                    **{field: getattr(result, field) for field in result.__dataclass_fields__ if field != "explanation"},
                    "explanation": Explanation(
                        **{**_empty_explanation_kwargs(query, mapping=result.mapping, edge_path_matches=result.edge_path_matches), "unmatched_query_nodes": ("n-other",)},
                    ),
                }
            )

    def test_compare_without_retrieval_still_carries_fail_closed_flags(self):
        engine = FakeEngine()
        query = graph_with_id("q")
        candidate = graph_with_id("c")
        result = engine.compare(query, candidate, mode="analogical")
        self.assertFalse(result.retrieval_flags.polarity_reliable)
        self.assertTrue(result.retrieval_flags.requires_structural_verification)

    def test_from_wire_rejects_missing_required_field(self):
        wire = FakeVerifier().verify(graph_with_id("q"), graph_with_id("c")).components.to_wire()
        wire.pop("R_direct_unweighted")
        with self.assertRaisesRegex(ValueError, "missing required score fields: R_direct_unweighted"):
            ScoreVector.from_wire(wire)

    def test_from_wire_rejects_unknown_top_level_field(self):
        wire = FakeVerifier().verify(graph_with_id("q"), graph_with_id("c")).components.to_wire()
        wire["N_rol"] = 0.1
        with self.assertRaisesRegex(ValueError, "unknown score field: N_rol"):
            ScoreVector.from_wire(wire)

    def test_from_wire_keeps_extension_diagnostics_only_under_extras(self):
        wire = FakeVerifier().verify(graph_with_id("q"), graph_with_id("c")).components.to_wire()
        wire["extras"] = {"generic_motif_margin": 0.2}
        restored = ScoreVector.from_wire(wire)
        self.assertEqual(restored.extras["generic_motif_margin"], 0.2)
        with self.assertRaisesRegex(ValueError, "unknown score field: generic_motif_margin"):
            ScoreVector.from_wire({**wire, "generic_motif_margin": 0.2})

    def test_edge_path_match_requires_parallel_node_provenance_and_matching_ids(self):
        qrp = ItemProvenance("q", "r0", "manual")
        crp = ItemProvenance("c", "r0a", "manual")
        with self.assertRaisesRegex(ValueError, "realized node IDs and provenances must be parallel"):
            EdgePathMatch("r0", ("r0a",), ("x0",), 1.0, qrp, (crp,))
        with self.assertRaisesRegex(ValueError, "EdgePathMatch.realizes_node provenance item_id"):
            EdgePathMatch("r0", ("r0a",), ("x0",), 1.0, qrp, (crp,), (ItemProvenance("c", "other", "manual"),))
        with self.assertRaisesRegex(ValueError, "EdgePathMatch.query provenance item_id"):
            EdgePathMatch("r0", ("r0a",), (), 1.0, ItemProvenance("q", "other", "manual"), (crp,))

    def test_verifier_rejects_non_injective_mapping(self):
        query = graph_with_id("q")
        candidate = graph_with_id("c")
        result = FakeVerifier().verify(query, candidate)
        duplicate = result.mapping + (
            NodeMatch(
                result.mapping[0].query_node,
                "n2",
                0.5,
                result.mapping[0].query_provenance,
                ItemProvenance(candidate.thought_id, "n2", candidate.provenance.kind, ()),
            ),
        )
        kwargs = {field: getattr(result, field) for field in result.__dataclass_fields__}
        kwargs["mapping"] = duplicate
        kwargs["explanation"] = Explanation(
            **{**_empty_explanation_kwargs(query, mapping=duplicate, edge_path_matches=result.edge_path_matches)}
        )
        with self.assertRaisesRegex(ValueError, "mapping query node IDs must be unique"):
            VerifierResult(**kwargs)
        two_to_one = (
            result.mapping[0],
            NodeMatch(
                "n2",
                result.mapping[0].candidate_node,
                0.5,
                ItemProvenance(query.thought_id, "n2", query.provenance.kind, ()),
                result.mapping[0].candidate_provenance,
            ),
        )
        kwargs["mapping"] = two_to_one
        kwargs["explanation"] = Explanation(
            **{**_empty_explanation_kwargs(query, mapping=two_to_one, edge_path_matches=result.edge_path_matches)}
        )
        with self.assertRaisesRegex(ValueError, "mapping candidate node IDs must be unique"):
            VerifierResult(**kwargs)

    def test_resonance_hit_rejects_mixed_candidate_ids(self):
        query = graph_with_id("q")
        candidate = graph_with_id("c")
        result = FakeVerifier().verify(query, candidate)
        other = CandidateResult(
            candidate_id="other",
            channel_scores={"structural": 0.8},
            channel_ranks={"structural": 1},
            seed_correspondences=(),
            usable_query_evidence=1.0,
            requires_structural_verification=True,
            polarity_reliable=False,
            index_version="i",
            feature_version="f",
            corpus_snapshot="s",
            config=CFG,
        )
        with self.assertRaisesRegex(ValueError, "hit candidate_id must match verification.candidate_id"):
            ResonanceHit(other, result)

    def test_from_wire_rejects_bool_nan_and_numeric_strings(self):
        wire = FakeVerifier().verify(graph_with_id("q"), graph_with_id("c")).components.to_wire()
        with self.assertRaisesRegex(ValueError, "N_role must be a finite number"):
            ScoreVector.from_wire({**wire, "N_role": True})
        with self.assertRaisesRegex(ValueError, "R_direct must be finite"):
            ScoreVector.from_wire({**wire, "R_direct": math.nan})
        with self.assertRaisesRegex(ValueError, "S_semantic must be a finite number"):
            ScoreVector.from_wire({**wire, "S_semantic": "0.7"})

    def test_v0_1_modes_are_frozen(self):
        self.assertEqual(RESONANCE_MODES, ("structural", "analogical", "complementary"))
        self.assertEqual(require_mode("analogical"), "analogical")
        with self.assertRaisesRegex(ValueError, "unsupported resonance mode"):
            require_mode("blend")
        engine = FakeEngine()
        query = engine.ingest("query", source_id="q")
        engine.index(graph_with_id("c"))
        with self.assertRaisesRegex(ValueError, "unsupported resonance mode"):
            engine.find(query, mode="semantic", k=5)

    def test_verifier_rejects_duplicate_relations_and_mapped_unmatched_overlap(self):
        query = graph_with_id("q")
        candidate = graph_with_id("c")
        result = FakeVerifier().verify(query, candidate)
        rel = RelationMatch(
            "r1",
            "r1",
            1.0,
            ItemProvenance(query.thought_id, "r1", query.provenance.kind, ()),
            ItemProvenance(candidate.thought_id, "r1", candidate.provenance.kind, ()),
        )
        duplicated = (rel, rel)
        kwargs = {field: getattr(result, field) for field in result.__dataclass_fields__}
        kwargs["matched_relations"] = duplicated
        kwargs["explanation"] = Explanation(
            **{
                **_empty_explanation_kwargs(
                    query, mapping=result.mapping, matched_relations=duplicated, edge_path_matches=result.edge_path_matches
                )
            }
        )
        with self.assertRaisesRegex(ValueError, "matched query relation IDs must be unique"):
            VerifierResult(**kwargs)
        overlap_nodes = ("n1",)
        kwargs = {field: getattr(result, field) for field in result.__dataclass_fields__}
        kwargs["unmatched_query_nodes"] = overlap_nodes
        kwargs["explanation"] = Explanation(
            **{
                **_empty_explanation_kwargs(query, mapping=result.mapping, edge_path_matches=result.edge_path_matches),
                "unmatched_query_nodes": overlap_nodes,
            }
        )
        with self.assertRaisesRegex(ValueError, "mapped and unmatched query nodes must be disjoint"):
            VerifierResult(**kwargs)

    def test_runtime_floor_is_python_3_10(self):
        self.assertEqual(MINIMUM_PYTHON, (3, 10))
        self.assertGreaterEqual(sys.version_info[:2], MINIMUM_PYTHON)


if __name__ == "__main__":
    unittest.main()
