"""R6 transport tests: MCP framing, tool schemas, pass-through discipline,
manual-DNA-without-LLM, persistence tools, and a real stdio subprocess smoke."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.graph import ThoughtGraph
from src.mcp import MCPServer, ResonanceAdapter, TOOLS

V01 = REPO / "benchmark" / "r0-v0.1"


def frozen_graph(index=0):
    line = (V01 / "graphs.jsonl").read_text().splitlines()[index]
    return json.loads(line)["thought_dna"]


def rpc(server, method, params=None, msg_id=1):
    import io
    frames = [{"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}},
              {"jsonrpc": "2.0", "id": msg_id, "method": method,
               **({"params": params} if params is not None else {})}]
    out = io.StringIO()
    server.serve(io.StringIO("\n".join(json.dumps(f) for f in frames) + "\n"), out)
    return json.loads(out.getvalue().splitlines()[-1])


def call_tool(server, name, arguments):
    reply = rpc(server, "tools/call", {"name": name, "arguments": arguments})
    result = reply["result"]
    payload = json.loads(result["content"][0]["text"])
    return result["isError"], payload


class SchemaTests(unittest.TestCase):
    def test_required_operations_are_all_present(self):
        names = {t["name"] for t in TOOLS}
        for required in ("ingest_thought", "index_thought", "find_resonance",
                         "compare_thoughts", "explain_resonance", "get_thought"):
            self.assertIn(required, names)
        for tool in TOOLS:
            self.assertIn("inputSchema", tool)
            self.assertEqual(tool["inputSchema"]["type"], "object")
            self.assertFalse(tool["inputSchema"].get("additionalProperties", True))

    def test_handlers_are_pass_through_only(self):
        """No retrieval/alignment/scoring logic may live in transport: the
        adapter source must not import those implementation modules' internals
        beyond the facade, and must contain no scoring arithmetic."""
        import inspect
        import src.mcp.adapter as adapter
        src_text = inspect.getsource(adapter)
        for forbidden in ("src.alignment", "src.index.store", "src.fingerprint",
                          "src.scoring", "solve_fgw", "adjudicate("):
            self.assertNotIn(forbidden, src_text)


class ToolFlowTests(unittest.TestCase):
    def setUp(self):
        self.server = MCPServer(ResonanceAdapter())

    def test_manual_thought_dna_works_without_llm(self):
        manual = frozen_graph(0)                       # frozen manual graphs
        err, payload = call_tool(self.server, "index_thought", {"thought": manual})
        self.assertFalse(err)
        self.assertTrue(payload["indexed"])
        err, got = call_tool(self.server, "get_thought",
                             {"thought_id": payload["thought_id"]})
        self.assertFalse(err)
        self.assertEqual(got["thought"], ThoughtGraph.from_dict(manual).to_dict())

    def test_find_compare_explain_round_trip_with_metadata(self):
        a, b = frozen_graph(0), frozen_graph(1)
        call_tool(self.server, "index_thought", {"thought": b})
        err, found = call_tool(self.server, "find_resonance",
                               {"thought": a, "mode": "structural", "k": 5})
        self.assertFalse(err)
        for key in ("adapter_version", "engine_version", "interface_version",
                    "verifier_config_hash", "corpus_snapshot"):
            self.assertIn(key, found["metadata"])
        if found["hits"]:
            hit = found["hits"][0]
            self.assertIn("components", hit["verification"])
            self.assertIn("structural_score", hit["verification"]["components"])
            self.assertIn("mapping", hit["verification"])
        err, cmp_ = call_tool(self.server, "compare_thoughts",
                              {"a": a, "b": b, "mode": "structural"})
        self.assertFalse(err)
        self.assertIn("explanation", cmp_["result"])
        a_id = cmp_["result"]["query_id"]; b_id = cmp_["result"]["candidate_id"]
        err, exp = call_tool(self.server, "explain_resonance",
                             {"a_id": a_id, "b_id": b_id})
        self.assertFalse(err)
        self.assertEqual(exp["result"]["classification"],
                         cmp_["result"]["classification"])

    def test_unknown_mode_surfaces_engine_error(self):
        err, payload = call_tool(self.server, "find_resonance",
                                 {"thought": frozen_graph(0), "mode": "semantic"})
        self.assertTrue(err)
        self.assertIn("unsupported resonance mode", payload["message"])

    def test_snapshot_tools_round_trip_and_fail_closed(self):
        call_tool(self.server, "index_thought", {"thought": frozen_graph(0)})
        with tempfile.TemporaryDirectory() as tmp:
            err, _ = call_tool(self.server, "save_snapshot", {"directory": tmp})
            self.assertFalse(err)
            err, payload = call_tool(self.server, "load_snapshot", {"directory": tmp})
            self.assertFalse(err)
            manifest = Path(tmp) / "manifest.json"
            data = json.loads(manifest.read_text())
            data["verifier_version"] = "forged/9.9"
            manifest.write_text(json.dumps(data, sort_keys=True,
                                           separators=(",", ":")) + "\n")
            err, payload = call_tool(self.server, "load_snapshot", {"directory": tmp})
            self.assertTrue(err)
            self.assertEqual(payload["error"], "EngineIntegrityError")


class StdioSubprocessTests(unittest.TestCase):
    def test_real_stdio_round_trip(self):
        frames = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "ingest_thought",
                        "arguments": {"context": "Heat causes failure."}}},
        ]
        proc = subprocess.run(
            [sys.executable, "-m", "src.mcp.server"],
            input="\n".join(json.dumps(f) for f in frames) + "\n",
            capture_output=True, text=True, cwd=REPO, timeout=60)
        replies = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual(len(replies), 3)
        self.assertEqual(replies[0]["result"]["protocolVersion"], "2024-11-05")
        self.assertEqual(len(replies[1]["result"]["tools"]), len(TOOLS))
        body = json.loads(replies[2]["result"]["content"][0]["text"])
        self.assertIn("thought", body)
        self.assertEqual(body["thought"]["provenance"]["kind"], "extracted")


if __name__ == "__main__":
    unittest.main()
