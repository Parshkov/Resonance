"""R8 discovery tests: consent filtering, leak-safety, no-compensation,
schema strictness, provenance, wire exposure, and error behavior."""

import copy
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.discovery import ConsentRegistry, DiscoveryService
from src.discovery.fixtures.demo_corpus import TEXTS, build_engine
from src.discovery.fixtures.metadata_payload import METADATA_PAYLOAD


def make_service(metadata=None, drop_sessions=()):
    engine, tids = build_engine()
    payload = copy.deepcopy(metadata or METADATA_PAYLOAD)
    payload["sessions"] = [dict(r) for r in payload["sessions"]
                           if r["session_id"] not in drop_sessions]
    for record in payload["sessions"]:
        record["session_id"] = tids[record["session_id"]]
    return engine, tids, DiscoveryService(engine, ConsentRegistry.from_payload(payload))


class ConsentAndLeakTests(unittest.TestCase):
    def test_hidden_session_is_absent_and_uninferable(self):
        """THE leak test: the full response with the hidden resonant session
        present must equal the response with that session absent from the
        corpus metadata entirely -- matches, rejected, aggregation, counts."""
        engine_a, tids_a, svc_a = make_service()
        resp_a = svc_a.discover(engine_a.get(tids_a["s-battery"]), mode="analogical", k=10)
        engine_b, tids_b, svc_b = make_service(drop_sessions={"s-hidden-market"})
        resp_b = svc_b.discover(engine_b.get(tids_b["s-battery"]), mode="analogical", k=10)
        self.assertEqual(json.dumps(resp_a, sort_keys=True),
                         json.dumps(resp_b, sort_keys=True))
        self.assertTrue(all(m["person_pseudonym"] != "willow"
                            for m in resp_a["matches"] + resp_a["rejected"]))

    def test_unshareable_location_never_appears_anywhere(self):
        engine, tids, svc = make_service()
        resp = svc.discover(engine.get(tids["s-battery"]), mode="analogical", k=10)
        cedar = next(m for m in resp["rejected"] if m["person_pseudonym"] == "cedar")
        self.assertNotIn("location_bucket", cedar["display"])
        self.assertNotIn("grid-east",
                         json.dumps([b for b in resp["aggregation"]["buckets"]
                                     if b["bucket_id"] != "grid-east"]))

    def test_no_direct_identifiers_on_the_wire(self):
        engine, tids, svc = make_service()
        blob = json.dumps(svc.discover(engine.get(tids["s-battery"]),
                                       mode="analogical", k=10))
        for banned in ("email", "phone", "@", "s-hidden-market"):
            self.assertNotIn(banned, blob)


class NoCompensationTests(unittest.TestCase):
    def test_display_metadata_cannot_change_ranking(self):
        """Permute locations/topics/pseudonyms of discoverable sessions: the
        sequence of (session order, classification, scores) must not move."""
        engine_a, tids_a, svc_a = make_service()
        resp_a = svc_a.discover(engine_a.get(tids_a["s-battery"]), mode="analogical", k=10)
        mutated = copy.deepcopy(METADATA_PAYLOAD)
        for record in mutated["sessions"]:
            if record["share_state"] == "discoverable":
                record["location_bucket"] = "grid-mars"
                record["location_shareable"] = bool(record.get("location_shareable"))
                record["topic_tag"] = "swapped"
                record["person_pseudonym"] = record["person_pseudonym"].upper()
        engine_b, tids_b, svc_b = make_service(metadata=mutated)
        resp_b = svc_b.discover(engine_b.get(tids_b["s-battery"]), mode="analogical", k=10)
        key = lambda r: [(m["session_id"], m["mode_classification"],
                          m["scores"]) for m in r["matches"]]
        self.assertEqual(key(resp_a), key(resp_b))

    def test_segregation_is_driven_only_by_engine_hard_rejection(self):
        engine, tids, svc = make_service()
        resp = svc.discover(engine.get(tids["s-battery"]), mode="analogical", k=10)
        for m in resp["matches"]:
            self.assertIsNone(m["hard_rejection"])
        for m in resp["rejected"]:
            self.assertIsNotNone(m["hard_rejection"])

    def test_service_source_contains_no_engine_logic(self):
        for module in ("service.py", "mcp.py", "metadata.py"):
            text = (REPO / "src" / "discovery" / module).read_text()
            for forbidden in ("src.alignment", "src.index.store", "src.fingerprint",
                              "src.scoring", "solve_fgw", "adjudicate(",
                              "sort(", "sorted(match", "reverse=True"):
                self.assertNotIn(forbidden, text, module)


class ContractTests(unittest.TestCase):
    def test_flagship_gate_two_to_four_useful_matches_with_evidence(self):
        engine, tids, svc = make_service()
        resp = svc.discover(engine.get(tids["s-battery"]), mode="analogical", k=10)
        useful = [m for m in resp["matches"]
                  if m["evidence"]["mapped_node_count"] >= 4
                  and m["evidence"]["top_correspondences"]]
        self.assertGreaterEqual(len(useful), 2)
        self.assertLessEqual(len(useful), 4)
        for m in useful:
            self.assertTrue(m["evidence"]["preserved_relations"])
            self.assertIn("provenance", resp["query"])

    def test_provenance_pins_engine_identity(self):
        engine, tids, svc = make_service()
        resp = svc.discover(engine.get(tids["s-battery"]), mode="analogical", k=5)
        prov = resp["query"]["provenance"]
        self.assertEqual(prov["verifier_config_hash"], engine.verifier.config_hash)
        self.assertEqual(prov["corpus_snapshot"],
                         engine.candidate_index.corpus_snapshot)

    def test_metadata_schema_is_strict(self):
        bad = copy.deepcopy(METADATA_PAYLOAD)
        bad["sessions"][0]["surprise"] = 1
        with self.assertRaises(ValueError):
            ConsentRegistry.from_payload(bad)
        bad2 = copy.deepcopy(METADATA_PAYLOAD)
        bad2["schema_version"] = "other/9.9"
        with self.assertRaises(ValueError):
            ConsentRegistry.from_payload(bad2)

    def test_unknown_mode_and_unknown_match_id_raise(self):
        engine, tids, svc = make_service()
        with self.assertRaises(ValueError):
            svc.discover(engine.get(tids["s-battery"]), mode="semantic")
        with self.assertRaises(ValueError):
            svc.request_intro("nope")

    def test_intro_event_discloses_nothing_and_audits_deterministically(self):
        engine, tids, svc = make_service()
        resp = svc.discover(engine.get(tids["s-battery"]), mode="analogical", k=5)
        event = svc.request_intro(resp["matches"][0]["match_id"], "hello")
        self.assertEqual(event["state"], "pending_target_acceptance")
        blob = json.dumps(svc.audit_log())
        self.assertNotIn("_target_session", blob)
        self.assertNotIn("hello", blob)

    def test_determinism(self):
        engine, tids, svc = make_service()
        q = engine.get(tids["s-battery"])
        a = svc.discover(q, mode="analogical", k=10)
        b = svc.discover(q, mode="analogical", k=10)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))


class WireTests(unittest.TestCase):
    def test_discover_tool_over_the_wire_and_r6_tools_intact(self):
        import io
        from src.discovery.demo_server import DiscoveryMCPServer, build_service
        from src.discovery.mcp import DiscoveryAdapter, TOOLS
        from src.mcp.adapter import TOOLS as BASE_TOOLS
        self.assertEqual(len(TOOLS), len(BASE_TOOLS) + 1)
        self.assertEqual([t["name"] for t in TOOLS[:len(BASE_TOOLS)]],
                         [t["name"] for t in BASE_TOOLS])
        svc = build_service()
        server = DiscoveryMCPServer(DiscoveryAdapter(svc))
        query = next(g for g in (svc.engine.get(p.session_id)
                                 for p in svc.registry._profiles.values())
                     if g and "Strong heat causes degradation" in g.source.text)
        frames = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                  {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                   "params": {"name": "discover_resonance",
                              "arguments": {"thought": query.to_dict(),
                                            "mode": "analogical", "k": 10}}}]
        out = io.StringIO()
        server.serve(io.StringIO("\n".join(json.dumps(f) for f in frames) + "\n"), out)
        body = json.loads(json.loads(out.getvalue().splitlines()[1])
                          ["result"]["content"][0]["text"])
        self.assertGreaterEqual(len(body["matches"]), 2)
        self.assertTrue(all(m["person_pseudonym"] != "willow" for m in body["matches"]))


if __name__ == "__main__":
    unittest.main()
