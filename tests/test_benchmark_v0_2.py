"""Benchmark v0.2 gates (ADR-0004): the engine must pass every gate on the
untouched S5-S8 split, and the extractor every prose gate. Fixture hashes are
pinned so a silent regeneration cannot move the goalposts."""

import hashlib
import importlib.util
import json
import sys
import unittest

from src.semantics import neural
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
V02 = REPO / "benchmark" / "r0-v0.2"
X02 = REPO / "benchmark" / "extraction-v0.2"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FixtureIntegrityTests(unittest.TestCase):
    def test_manifest_hashes_match_files_and_splits_are_disjoint_skeletons(self):
        manifest = json.loads((V02 / "manifest.json").read_text())
        for name, digest in manifest["files"].items():
            self.assertEqual(hashlib.sha256((V02 / name).read_bytes()).hexdigest(), digest, name)
        self.assertEqual(hashlib.sha256((V02 / "skeletons.py").read_bytes()).hexdigest(), manifest["skeletons_sha256"])
        self.assertFalse(set(manifest["splits"]["calibration"]) & set(manifest["splits"]["gate"]))
        self.assertEqual(manifest["counts"], {"graphs": 176, "pairs": 144, "skeletons": 8, "families": 18,
                                              "calibration_pairs": 72, "gate_pairs": 72})

    def test_generator_is_deterministic(self):
        build = _load(V02 / "build_fixtures.py", "v02_build")
        data = build.build()
        self.assertEqual(hashlib.sha256(build.jsonl(data["graphs"])).hexdigest(),
                         json.loads((V02 / "manifest.json").read_text())["files"]["graphs.jsonl"])

    def test_template_coincidence_labels_carry_no_abstract_concept(self):
        from src.semantics import abstract_concepts
        sk = _load(V02 / "skeletons.py", "v02_skeletons")
        for skeleton in sk.SKELETONS:
            for label in skeleton["coincidence"]:
                self.assertFalse(abstract_concepts(label), (skeleton["id"], label))


class EngineGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runner = _load(V02 / "runner.py", "v02_runner")
        cls.report = runner.evaluate()

    def test_all_gates_pass_on_the_gate_split(self):
        failing = {k: v for k, v in self.report["gates"].items() if v["status"] != "pass"}
        self.assertEqual(failing, {}, failing)
        self.assertEqual(self.report["overall_status"], "pass")

    def test_analogy_beats_template_coincidence_on_every_gate_skeleton(self):
        self.assertEqual(self.report["gate"]["analogy_over_coincidence"], 1.0)
        self.assertEqual(self.report["gate"]["negative_false_positive_rate"], 0.0)

    @unittest.skipIf(neural.active() is not None,
                     "the frozen report is the lexicon-only engine; an encoder is a different one")
    def test_frozen_report_matches_live_engine(self):
        frozen = json.loads((REPO / "src/engine/reports/r0-v0.2-e2e.json").read_text())
        for split in ("calibration", "gate"):
            live = {k: v for k, v in self.report[split].items() if k != "families"}
            saved = {k: v for k, v in frozen[split].items() if k != "families"}
            self.assertEqual(live, saved, split)


class ExtractionGateTests(unittest.TestCase):
    def test_prose_gates_pass(self):
        runner = _load(X02 / "runner.py", "x02_runner")
        report = runner.evaluate()
        failing = {k: v for k, v in report["gates"].items() if v["status"] != "pass"}
        self.assertEqual(failing, {}, failing)
        self.assertEqual(report["metrics"]["pii_leaks"], 0)
        self.assertEqual(report["metrics"]["determinism"], 1.0)


if __name__ == "__main__":
    unittest.main()
