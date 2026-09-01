"""Independent R6-MCP repeat: thin adapter, lifecycle, and persistence gates."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
V01 = REPO / "benchmark" / "r0-v0.1"


def load_benchmark_graphs():
    from src.graph import ThoughtGraph

    graphs = {}
    for line in (V01 / "graphs.jsonl").read_text(encoding="utf-8").splitlines():
        payload = json.loads(line)
        graphs[payload["benchmark_graph_id"]] = ThoughtGraph.from_dict(payload["thought_dna"])
    pairs = [json.loads(line) for line in (V01 / "pairs.jsonl").read_text(encoding="utf-8").splitlines()]
    return graphs, pairs


class MCPAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.mcp.adapter import ResonanceMCPAdapter, UnknownToolError

        cls.Adapter = ResonanceMCPAdapter
        cls.UnknownToolError = UnknownToolError
        cls.graphs, cls.pairs = load_benchmark_graphs()

    def setUp(self):
        self.adapter = self.Adapter()

    def test_tool_catalog_is_exact_deterministic_and_strict(self):
        tools = self.adapter.tools()
        self.assertEqual(
            [tool["name"] for tool in tools],
            [
                "ingest_thought",
                "index_thought",
                "find_resonance",
                "compare_thoughts",
                "explain_resonance",
                "get_thought",
            ],
        )
        for tool in tools:
            self.assertEqual(tool["inputSchema"]["type"], "object")
            self.assertFalse(tool["inputSchema"]["additionalProperties"])
            self.assertEqual(tool["outputSchema"]["type"], "object")
            self.assertFalse(tool["outputSchema"]["additionalProperties"])
        tools[0]["name"] = "mutated"
        self.assertEqual(self.adapter.tools()[0]["name"], "ingest_thought")

    def test_ingest_delegates_and_reports_versions(self):
        response = self.adapter.call_tool(
            "ingest_thought",
            {"context": "Heat causes failure.", "source_id": "mcp-repeat"},
        )
        self.assertFalse(response["isError"])
        payload = response["structuredContent"]
        self.assertEqual(payload["operation"], "ingest_thought")
        self.assertEqual(payload["result"]["source"]["text"], "Heat causes failure.")
        self.assertEqual(payload["result"]["provenance"]["kind"], "extracted")
        metadata = payload["metadata"]
        self.assertEqual(metadata["engine_version"], "resonance-engine/0.1")
        self.assertEqual(metadata["interface_version"], "resonance-interfaces/0.1")
        self.assertEqual(metadata["score_contract_version"], "resonance-score/0.1")

    def test_manual_thought_indexes_and_gets_without_an_llm(self):
        manual = json.loads(
            (REPO / "tests" / "fixtures" / "thought_dna" / "valid_manual.json").read_text(
                encoding="utf-8"
            )
        )
        indexed = self.adapter.call_tool("index_thought", {"thought": manual})
        self.assertFalse(indexed["isError"])
        self.assertEqual(indexed["structuredContent"]["result"]["thought"]["thought_id"], "t_manual")
        self.assertFalse(indexed["structuredContent"]["result"]["persisted"])
        fetched = self.adapter.call_tool("get_thought", {"id": "t_manual"})
        self.assertEqual(fetched["structuredContent"]["result"], indexed["structuredContent"]["result"]["thought"])

    def test_find_compare_and_explain_return_full_structured_evidence(self):
        pair = next(item for item in self.pairs if item["family"] == "paraphrase")
        query = self.graphs[pair["query_graph"]]
        candidate = self.graphs[pair["candidate_graph"]]
        self.adapter.call_tool("index_thought", {"thought": candidate.to_dict()})

        found = self.adapter.call_tool(
            "find_resonance",
            {"thought": query.to_dict(), "mode": "structural", "k": 5},
        )
        self.assertFalse(found["isError"])
        result = found["structuredContent"]["result"]
        self.assertEqual(result["query_id"], query.thought_id)
        self.assertEqual(result["returned"], 1)
        verification = result["hits"][0]["verification"]
        self.assertEqual(verification["candidate_id"], candidate.thought_id)
        self.assertIn("N_role", verification["components"])
        self.assertIn("mapping", verification["explanation"])
        self.assertTrue(verification["mapping"])
        self.assertIn("query_provenance", verification["mapping"][0])

        compared = self.adapter.call_tool(
            "compare_thoughts",
            {"a": {"id": query.thought_id}, "b": {"id": candidate.thought_id}, "mode": "structural"},
        )
        self.assertTrue(compared["isError"], "the unindexed query reference must fail visibly")
        compared = self.adapter.call_tool(
            "compare_thoughts",
            {"a": query.to_dict(), "b": {"id": candidate.thought_id}, "mode": "structural"},
        )
        self.assertFalse(compared["isError"])
        explained = self.adapter.call_tool(
            "explain_resonance",
            {"a": query.thought_id, "b": candidate.thought_id},
        )
        self.assertEqual(
            explained["structuredContent"]["result"],
            compared["structuredContent"]["result"],
        )

    def test_input_and_unknown_tool_failures_follow_mcp_error_split(self):
        bad = self.adapter.call_tool(
            "find_resonance",
            {"thought": {"id": "missing"}, "mode": "structural", "k": True},
        )
        self.assertTrue(bad["isError"])
        self.assertEqual(bad["structuredContent"]["error"]["type"], "ValueError")
        bad = self.adapter.call_tool("get_thought", {"id": "x", "extra": 1})
        self.assertTrue(bad["isError"])
        self.assertIn("unknown tool arguments", bad["structuredContent"]["error"]["message"])
        with self.assertRaises(self.UnknownToolError):
            self.adapter.call_tool("not_a_tool", {})

    def test_manifest_snapshot_autosaves_and_restart_loads(self):
        manual = json.loads(
            (REPO / "tests" / "fixtures" / "thought_dna" / "valid_manual.json").read_text(
                encoding="utf-8"
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            adapter = self.Adapter(data_dir=data_dir)
            indexed = adapter.call_tool("index_thought", {"thought": manual})
            self.assertFalse(indexed["isError"])
            self.assertTrue(indexed["structuredContent"]["result"]["persisted"])
            self.assertEqual(
                {path.name for path in data_dir.iterdir()},
                {"manifest.json", "store.json", "index.json"},
            )
            restarted = self.Adapter(data_dir=data_dir)
            fetched = restarted.call_tool("get_thought", {"id": "t_manual"})
            self.assertEqual(fetched["structuredContent"]["result"]["thought_id"], "t_manual")

            manifest_path = data_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["engine_version"] = "forged-engine/9.9"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            from src.engine import EngineIntegrityError

            with self.assertRaises(EngineIntegrityError):
                self.Adapter(data_dir=data_dir)

    def test_partial_snapshot_fails_closed_at_startup(self):
        from src.engine import EngineIntegrityError

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "store.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaises(EngineIntegrityError):
                self.Adapter(data_dir=Path(tmp))


class MCPProtocolTests(unittest.TestCase):
    def setUp(self):
        from src.mcp.adapter import ResonanceMCPAdapter
        from src.mcp.server import ResonanceMCPServer

        self.server = ResonanceMCPServer(ResonanceMCPAdapter())

    @staticmethod
    def initialize(server, protocol="2025-11-25"):
        return server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": protocol,
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0"},
                },
            }
        )

    def test_lifecycle_gates_tools_and_negotiates_versions(self):
        before = self.server.handle_message(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        self.assertEqual(before["error"]["code"], -32002)
        initialized = self.initialize(self.server)
        self.assertEqual(initialized["result"]["protocolVersion"], "2025-11-25")
        self.assertEqual(initialized["result"]["capabilities"], {"tools": {"listChanged": False}})
        self.assertIsNone(
            self.server.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"})
        )
        listed = self.server.handle_message(
            {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}
        )
        self.assertEqual(len(listed["result"]["tools"]), 6)

        fallback_server = type(self.server)(self.server.adapter)
        fallback = self.initialize(fallback_server, "unsupported-future-version")
        self.assertEqual(fallback["result"]["protocolVersion"], "2025-11-25")

    def test_unknown_tool_is_protocol_error_but_domain_failure_is_tool_result(self):
        self.initialize(self.server)
        self.server.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"})
        unknown = self.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "unknown", "arguments": {}},
            }
        )
        self.assertEqual(unknown["error"]["code"], -32602)
        domain = self.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "get_thought", "arguments": {"id": ""}},
            }
        )
        self.assertTrue(domain["result"]["isError"])

    def test_real_stdio_subprocess_is_clean_and_machine_readable(self):
        process = subprocess.Popen(
            [sys.executable, "-m", "src.mcp.server"],
            cwd=REPO,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        assert process.stdin is not None
        assert process.stdout is not None
        assert process.stderr is not None

        def request(payload, expect_response=True):
            process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
            process.stdin.flush()
            if not expect_response:
                return None
            line = process.stdout.readline()
            self.assertTrue(line, "server closed stdout before responding")
            return json.loads(line)

        initialized = request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "clean-subprocess", "version": "1"},
                },
            }
        )
        self.assertEqual(initialized["result"]["serverInfo"]["name"], "resonance")
        request(
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            expect_response=False,
        )
        listed = request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertEqual(len(listed["result"]["tools"]), 6)
        ingested = request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "ingest_thought",
                    "arguments": {"context": "Heat causes failure."},
                },
            }
        )
        self.assertFalse(ingested["result"]["isError"])
        self.assertEqual(
            ingested["result"]["structuredContent"]["result"]["source"]["text"],
            "Heat causes failure.",
        )
        process.stdin.close()
        self.assertEqual(process.wait(timeout=10), 0)
        self.assertEqual(process.stdout.read(), "")
        self.assertEqual(process.stderr.read(), "")
        process.stdout.close()
        process.stderr.close()


class MCPBoundaryTests(unittest.TestCase):
    def test_transport_imports_no_matching_component_internals(self):
        forbidden = {
            "src.alignment",
            "src.extraction",
            "src.fingerprint",
            "src.index",
            "src.scoring",
        }
        imported = set()
        for path in (REPO / "src" / "mcp").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
                elif isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
        offenders = sorted(
            module for module in imported if any(module == item or module.startswith(item + ".") for item in forbidden)
        )
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
