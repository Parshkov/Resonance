"""R6-E2E: clean MCP client acceptance over the accepted stdio adapter."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEMO = REPO / "demo"


def _source_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


class CleanClientBoundaryTests(unittest.TestCase):
    def test_demo_client_does_not_import_engine_or_mcp(self):
        for path in (DEMO / "client.py", DEMO / "run.py"):
            imported = _source_imports(path)
            self.assertNotIn("src", imported, path.name)
            for forbidden in ("engine", "alignment", "fingerprint", "index", "scoring", "mcp"):
                self.assertNotIn(forbidden, imported, f"{path.name} imported {forbidden}")


class DemoAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.TemporaryDirectory()
        cls.report_path = Path(cls.tmpdir.name) / "report.json"
        cls.transcript_path = Path(cls.tmpdir.name) / "transcript.jsonl"
        completed = subprocess.run(
            [sys.executable, str(DEMO / "run.py"),
             "--output", str(cls.report_path),
             "--transcript", str(cls.transcript_path)],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=120,
        )
        cls.proc = completed
        cls.report = json.loads(cls.report_path.read_text(encoding="utf-8")) if cls.report_path.exists() else {}

    @classmethod
    def tearDownClass(cls):
        cls.tmpdir.cleanup()

    def test_clean_client_run_passes(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)
        self.assertTrue(self.report.get("ok"), self.report)

    def test_discovers_required_tools(self):
        for name in ("ingest_thought", "index_thought", "find_resonance",
                     "compare_thoughts", "explain_resonance", "get_thought"):
            self.assertIn(name, self.report.get("tools") or [])

    def test_protocol_and_identity_match_accepted_r6(self):
        self.assertEqual(self.report.get("protocol"), "2024-11-05")
        identity = self.report.get("identity") or {}
        self.assertEqual(identity.get("adapter_version"), "resonance-mcp/0.1")
        self.assertEqual(identity.get("engine_version"), "resonance-engine/0.1")
        self.assertEqual(identity.get("interface_version"), "resonance-interfaces/0.1")
        self.assertEqual(
            identity.get("verifier_config_hash"),
            "3e107bc4850537730949d013ffa0f335b3ddbf9b0d64bb640fe34f893dbb1b1d",
        )

    def test_five_required_scenarios_and_error_diagnostics(self):
        by_id = {row["id"]: row for row in self.report.get("scenarios") or []}
        expected = {
            "S1-same-words-wrong-structure": "negative",
            "S2-cross-domain-analogy": "analogical",
            "S3a-partial-graph": "approximate",
            "S3b-transparent-granularity": "approximate",
            "S4-complementary-bridge": "complementary",
            "S5-polarity-inversion": "negative",
        }
        for sid, classification in expected.items():
            row = by_id[sid]
            self.assertTrue(row["ok"], (sid, row.get("failures")))
            self.assertEqual(row["classification"], classification)
            self.assertGreater(row.get("n_mapping") or 0, 0)
        self.assertTrue(by_id["S5-polarity-inversion"].get("hard_rejection"))
        self.assertTrue(by_id["S2-cross-domain-analogy"].get("find_hit"))
        self.assertTrue(by_id["U1-unsupported-mode"]["ok"])
        self.assertTrue(by_id["T1-unknown-method"]["ok"])

    def test_transcript_is_ndjson_mcp(self):
        lines = self.transcript_path.read_text(encoding="utf-8").splitlines()
        self.assertGreater(len(lines), 10)
        first = json.loads(lines[0])
        self.assertEqual(first["request"]["method"], "initialize")
        self.assertEqual(first["reply"]["result"]["protocolVersion"], "2024-11-05")


if __name__ == "__main__":
    unittest.main()
