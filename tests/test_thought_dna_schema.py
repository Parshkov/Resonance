import copy
import json
import unittest
from pathlib import Path

from src.graph import (
    ThoughtDNAValidationError,
    ThoughtGraph,
    canonical_json,
    canonical_sha256,
    make_node_id,
    make_relation_id,
    make_thought_id,
    validate_thought,
)

FIXTURES = Path(__file__).parent / "fixtures" / "thought_dna"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class ValidationTests(unittest.TestCase):
    def test_valid_fixtures(self):
        for name in ("valid_extracted.json", "valid_manual.json"):
            with self.subTest(name=name):
                self.assertEqual(validate_thought(load(name)), ())

    def test_committed_invalid_fixture_fails_for_intended_reason(self):
        with self.assertRaises(ThoughtDNAValidationError) as ctx:
            validate_thought(load("invalid_ungrounded_extracted.json"))
        self.assertIn("must not be empty", str(ctx.exception))

    def test_cross_field_failures_are_attributed(self):
        base = load("valid_extracted.json")
        cases = []

        x = copy.deepcopy(base)
        x["schema_version"] = "thought-dna/9.9"
        cases.append((x, "schema_version"))

        x = copy.deepcopy(base)
        x["source"]["sha256"] = "0" * 64
        cases.append((x, "sha256"))

        x = copy.deepcopy(base)
        x["relations"][0]["target"] = "missing"
        cases.append((x, "existing node"))

        x = copy.deepcopy(base)
        x["relations"][1]["type"] = "increases"
        cases.append((x, "type"))

        x = copy.deepcopy(base)
        x["nodes"][1]["id"] = "n_heat"
        cases.append((x, "duplicate node id"))

        x = copy.deepcopy(base)
        x["nodes"][0]["spans"][0]["text"] = "wrong"
        cases.append((x, "source.text[start:end]"))

        x = copy.deepcopy(base)
        x["nodes"][0]["knowledge"]["about"][0]["conf"] = 0.49
        cases.append((x, "[0.5,1]"))

        for raw, needle in cases:
            with self.subTest(needle=needle):
                with self.assertRaises(ThoughtDNAValidationError) as ctx:
                    validate_thought(raw)
                self.assertIn(needle, str(ctx.exception))

        manual = load("valid_manual.json")
        manual["provenance"]["extractor"] = {"id": "x", "version": "1"}
        with self.assertRaises(ThoughtDNAValidationError) as ctx:
            validate_thought(manual)
        self.assertIn("must be null", str(ctx.exception))

    def test_unknown_version_never_silently_coerces(self):
        raw = load("valid_extracted.json")
        raw["schema_version"] = "thought-dna/9.9"
        with self.assertRaises(ThoughtDNAValidationError) as ctx:
            ThoughtGraph.from_dict(raw)
        self.assertIn("unsupported schema_version", str(ctx.exception))


class CanonicalizationTests(unittest.TestCase):
    def test_permutation_invariant_serialization(self):
        original = load("valid_extracted.json")
        permuted = copy.deepcopy(original)
        permuted["nodes"].reverse()
        permuted["relations"].reverse()
        permuted["nodes"][-1]["knowledge"]["about"].reverse()
        for n in permuted["nodes"]:
            n["spans"].reverse()
        for r in permuted["relations"]:
            r["spans"].reverse()
            if "provenance_refs" in r:
                r["provenance_refs"].reverse()
        self.assertEqual(canonical_json(original), canonical_json(permuted))
        self.assertEqual(canonical_sha256(original), canonical_sha256(permuted))

    def test_round_trip_preserves_direction_polarity_modality_provenance(self):
        raw = load("valid_extracted.json")
        graph = ThoughtGraph.from_dict(raw)
        out = graph.to_dict()
        rel = next(r for r in out["relations"] if r["id"] == "r_prevents")
        self.assertEqual((rel["source"], rel["target"]), ("n_deg", "n_failure"))
        self.assertEqual(rel["type"], "prevents")
        self.assertEqual(rel["assertion"], "asserted")
        self.assertEqual(rel["modality"], "conditional")
        self.assertEqual(out["provenance"]["extractor"]["id"], "fixture-extractor")
        self.assertEqual(out["schema_version"], "thought-dna/0.1")
        self.assertEqual(
            canonical_json(out),
            canonical_json(ThoughtGraph.from_dict(out).to_dict()),
        )

    def test_defaults_materialize_in_canonical_output(self):
        raw = load("valid_extracted.json")
        rel = next(r for r in raw["relations"] if r["id"] == "r_causes")
        self.assertNotIn("assertion", rel)
        out = ThoughtGraph.from_dict(raw).to_dict()
        rel2 = next(r for r in out["relations"] if r["id"] == "r_causes")
        self.assertEqual(rel2["assertion"], "asserted")
        self.assertEqual(rel2["modality"], "actual")


class StableIdTests(unittest.TestCase):
    def test_deterministic_helpers(self):
        text = "abc"
        self.assertEqual(make_thought_id(text), make_thought_id(text))
        span = [{"start": 0, "end": 1, "text": "a"}]
        self.assertEqual(
            make_node_id("problem", spans=span),
            make_node_id("problem", spans=list(reversed(span))),
        )

    def test_relation_id_changes_with_direction_and_polarity(self):
        span = [{"start": 1, "end": 2, "text": "x"}]
        a = make_relation_id("n1", "n2", "causes", spans=span)
        b = make_relation_id("n2", "n1", "causes", spans=span)
        c = make_relation_id("n1", "n2", "prevents", spans=span)
        d = make_relation_id("n1", "n2", "causes", spans=span, assertion="negated")
        self.assertEqual(len({a, b, c, d}), 4)

    def test_manual_id_requires_stable_key(self):
        with self.assertRaises(ValueError):
            make_node_id("problem")
        self.assertEqual(
            make_node_id("problem", manual_key="p1"),
            make_node_id("problem", manual_key="p1"),
        )


if __name__ == "__main__":
    unittest.main()
