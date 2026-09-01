#!/usr/bin/env python3
"""Run the R6-E2E clean-client demo against the accepted MCP stdio server.

Uses only the standard library plus demo/client.py. Thought DNA documents are
read as JSON from the frozen v0.1 corpus; the client never imports src.engine
or src.mcp.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

DEMO = Path(__file__).resolve().parent
REPO = DEMO.parent
if str(DEMO) not in sys.path:
    sys.path.insert(0, str(DEMO))

from client import MCPClient, classify_reply, start_server, stop_server  # noqa: E402


def load_graphs(path: Path) -> dict[str, dict[str, Any]]:
    graphs: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        graphs[record["benchmark_graph_id"]] = record["thought_dna"]
    return graphs


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cmp(actual: Any, spec: dict[str, Any]) -> str | None:
    if "eq" in spec and actual != spec["eq"]:
        return f"{actual!r} != {spec['eq']!r}"
    if "gt" in spec and not (actual > spec["gt"]):
        return f"{actual!r} !> {spec['gt']!r}"
    if "gte" in spec and not (actual >= spec["gte"]):
        return f"{actual!r} !>= {spec['gte']!r}"
    if "lt" in spec and not (actual < spec["lt"]):
        return f"{actual!r} !< {spec['lt']!r}"
    return None


def check_compare(payload: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    result = payload.get("result") or {}
    if result.get("classification") != expect.get("classification"):
        failures.append(
            f"classification {result.get('classification')!r} != {expect.get('classification')!r}"
        )
    if expect.get("hard_rejection_present") and not result.get("hard_rejection"):
        failures.append("expected hard_rejection to be present")
    components = result.get("components") or {}
    for name, spec in (expect.get("components") or {}).items():
        miss = _cmp(components.get(name), spec)
        if miss:
            failures.append(f"component {name}: {miss}")
    if expect.get("containment_gt_symmetric"):
        qc = components.get("Q_containment")
        qs = components.get("Q_symmetric")
        if not (isinstance(qc, (int, float)) and isinstance(qs, (int, float)) and qc > qs):
            failures.append(f"Q_containment {qc!r} !> Q_symmetric {qs!r}")
    if expect.get("complement_positive"):
        kq = components.get("K_comp_q_to_c") or 0
        kc = components.get("K_comp_c_to_q") or 0
        if max(kq, kc) <= 0:
            failures.append(f"complement scores not positive: {kq}, {kc}")
    explanation = result.get("explanation") or {}
    if "mapping" not in result or "explanation" not in result:
        failures.append("missing mapping/explanation")
    if "provenance_kind" not in json.dumps(result.get("mapping") or []):
        # mapping entries carry query/candidate provenance objects
        if result.get("mapping"):
            first = result["mapping"][0]
            if "query_provenance" not in first:
                failures.append("mapping lacks provenance")
    meta = payload.get("metadata") or {}
    for key in ("adapter_version", "engine_version", "interface_version",
                "verifier_config_hash", "corpus_snapshot"):
        if key not in meta:
            failures.append(f"metadata missing {key}")
    if not explanation and result.get("classification"):
        failures.append("empty explanation")
    return failures


def check_identity(meta: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    failures = []
    for key, value in expected.items():
        if meta.get(key) != value:
            failures.append(f"identity {key}: {meta.get(key)!r} != {value!r}")
    return failures


def run(repo: Path = REPO) -> dict[str, Any]:
    spec = json.loads((DEMO / "scenarios.json").read_text(encoding="utf-8"))
    corpus = repo / spec["corpus"]
    actual_hash = file_sha256(corpus)
    if actual_hash != spec["graphs_sha256"]:
        raise SystemExit(
            f"frozen corpus hash mismatch: {actual_hash} != {spec['graphs_sha256']}"
        )
    graphs = load_graphs(corpus)

    proc = start_server(repo)
    client = MCPClient(proc)
    report: dict[str, Any] = {
        "ok": True,
        "scenarios": [],
        "identity": None,
        "tools": [],
        "corpus_sha256": actual_hash,
    }
    try:
        init = client.initialize()
        report["protocol"] = (init.get("result") or {}).get("protocolVersion")
        ping = classify_reply(client.ping())
        if not ping["ok"] or ping.get("reply", {}).get("result") != {}:
            report["ok"] = False
            report["ping"] = ping
        listed = client.list_tools()
        tools = [t["name"] for t in (listed.get("result") or {}).get("tools") or []]
        report["tools"] = tools
        missing = [name for name in spec["required_tools"] if name not in tools]
        if missing:
            report["ok"] = False
            report["missing_tools"] = missing

        identity_meta = None
        for scenario in spec["scenarios"]:
            entry: dict[str, Any] = {"id": scenario["id"], "title": scenario["title"], "ok": True, "failures": []}
            kind = scenario.get("kind", "compare")
            if kind == "transport_unknown_method":
                classified = classify_reply(client.request("definitely_not_a_method"))
                exp = scenario["expect_error"]
                if classified.get("stage") != exp["stage"] or classified.get("code") != exp["code"]:
                    entry["ok"] = False
                    entry["failures"].append(
                        f"transport error {classified.get('stage')} {classified.get('code')} "
                        f"!= {exp['stage']} {exp['code']}"
                    )
                entry["result"] = classified
            elif kind == "unsupported_mode":
                query = graphs[scenario["query_graph"]]
                candidate = graphs[scenario["candidate_graph"]]
                classified = client.call_tool(
                    "compare_thoughts",
                    {"a": query, "b": candidate, "mode": scenario["mode"]},
                )
                exp = scenario["expect_error"]
                if classified.get("stage") != exp["stage"]:
                    entry["ok"] = False
                    entry["failures"].append(f"stage {classified.get('stage')} != {exp['stage']}")
                if exp.get("message_contains") not in (classified.get("message") or ""):
                    entry["ok"] = False
                    entry["failures"].append(f"message {classified.get('message')!r}")
                entry["result"] = {k: classified[k] for k in ("ok", "stage", "message", "error_type") if k in classified}
            else:
                query = graphs[scenario["query_graph"]]
                candidate = graphs[scenario["candidate_graph"]]
                classified = client.call_tool(
                    "compare_thoughts",
                    {"a": query, "b": candidate, "mode": scenario["mode"]},
                )
                if not classified["ok"]:
                    entry["ok"] = False
                    entry["failures"].append(f"compare failed: {classified}")
                else:
                    payload = classified["payload"]
                    identity_meta = payload.get("metadata")
                    entry["failures"].extend(check_compare(payload, scenario["expect"]))
                    entry["failures"].extend(check_identity(payload.get("metadata") or {}, spec["identity"]))
                    result = payload.get("result") or {}
                    entry["classification"] = result.get("classification")
                    entry["hard_rejection"] = result.get("hard_rejection")
                    entry["n_mapping"] = len(result.get("mapping") or [])
                    entry["n_contradictions"] = len(result.get("contradictions") or [])
                    entry["metadata"] = payload.get("metadata")
                    if scenario.get("also_find"):
                        client.call_tool("index_thought", {"thought": candidate})
                        found = client.call_tool(
                            "find_resonance",
                            {"thought": query, "mode": scenario["mode"], "k": 20},
                        )
                        if not found["ok"]:
                            entry["failures"].append(f"find failed: {found}")
                        else:
                            hits = found["payload"].get("hits") or []
                            cand_id = candidate.get("thought_id")
                            hit_ids = [h.get("candidate", {}).get("candidate_id") for h in hits]
                            if cand_id not in hit_ids:
                                # Frozen v0.1 analogical find over a 1-graph index should
                                # still return that graph. A miss is an E2E failure.
                                entry["failures"].append(f"find missed candidate {cand_id}; hits={hit_ids}")
                            else:
                                entry["find_hit"] = True
                                cfg = hits[0]["candidate"].get("config") or {}
                                for key in ("component", "component_version", "config_hash", "schema_version"):
                                    if key not in cfg:
                                        entry["failures"].append(f"hit config missing {key}")
                if entry["failures"]:
                    entry["ok"] = False
            report["scenarios"].append(entry)
            if not entry["ok"]:
                report["ok"] = False
        report["identity"] = identity_meta
    finally:
        stop_server(proc)

    transcript_path = DEMO / "transcript.jsonl"
    transcript_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in client.transcript),
        encoding="utf-8",
    )
    report["transcript"] = str(transcript_path.relative_to(repo))
    report["n_frames"] = len(client.transcript)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEMO / "report.json")
    parser.add_argument("--transcript", type=Path, default=None)
    args = parser.parse_args()
    report = run()
    transcript_src = REPO / report["transcript"]
    if args.transcript is not None:
        args.transcript.write_bytes(transcript_src.read_bytes())
        report["transcript"] = str(args.transcript)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "output": str(args.output), "transcript": report.get("transcript")}, indent=2))
    if not report["ok"]:
        for scenario in report["scenarios"]:
            if not scenario["ok"]:
                print(scenario["id"], scenario["failures"], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
