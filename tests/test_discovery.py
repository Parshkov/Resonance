"""R8 discovery tests over the ACCEPTED R7 corpus: consent filtering,
leak-safety, no-compensation, schema/provenance strictness, wire exposure."""

import copy
import io
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from demo.corpus.discovery import is_discoverable, load_sessions
from src.discovery import ConsentRegistry, DiscoveryService
from src.discovery.fixtures.r7_corpus import FLAGSHIP_SESSION_ID, build, flagship_query

SESSIONS = load_sessions()
HIDDEN_IDS = [s["session_id"] for s in SESSIONS if not is_discoverable(s)]


def make_service(sessions=None):
    engine, registry, by_session = build(sessions)
    return DiscoveryService(engine, registry), by_session


def flagship_response(svc, by_session, k=15):
    return svc.discover(flagship_query(by_session), mode="analogical", k=k)


class ConsentAndLeakTests(unittest.TestCase):
    def test_hidden_sessions_are_absent_and_uninferable(self):
        """THE leak test on frozen data: responses with hidden sessions in
        the corpus vs with them deleted entirely must be identical JSON --
        matches, rejected, aggregation, every count. ses-ravi-irrigation is
        deliberately IN the flagship cluster."""
        self.assertIn("ses-ravi-irrigation", HIDDEN_IDS)
        svc_a, by_a = make_service()
        resp_a = flagship_response(svc_a, by_a)
        pruned = [s for s in SESSIONS if s["session_id"] not in HIDDEN_IDS]
        svc_b, by_b = make_service(pruned)
        resp_b = flagship_response(svc_b, by_b)
        self.assertEqual(json.dumps(resp_a, sort_keys=True),
                         json.dumps(resp_b, sort_keys=True))
        blob = json.dumps(resp_a).lower()
        for hidden in ("ravi", "nico", "irrigation", "tracing-private"):
            self.assertNotIn(hidden, blob)

    def test_location_absent_unless_consented(self):
        svc, by_session = make_service()
        no_loc = {s["thought_dna"]["thought_id"] for s in SESSIONS
                  if is_discoverable(s) and not s["consent"]["share_coarse_location"]}
        resp = flagship_response(svc, by_session)
        for entry in resp["matches"] + resp["rejected"]:
            profile = svc.registry.get(entry["session_id"]) if False else None
            if any(entry["session_id"] == s["session_id"] for s in SESSIONS
                   if s["thought_dna"]["thought_id"] in no_loc):
                self.assertNotIn("location", entry["display"])

    def test_anonymous_profile_fallback_is_respected(self):
        """A session with share_display_profile=false must appear as
        'anonymous', never with its real display label."""
        mutated = copy.deepcopy(SESSIONS)
        target_label = None
        for s in mutated:
            if s["session_id"] == "ses-gabe-warehouse":
                s["consent"]["share_display_profile"] = False
                target_label = s["person"]["display_label"]
        svc, by_session = make_service(mutated)
        resp = flagship_response(svc, by_session)
        gabe = [m for m in resp["matches"]
                if m["session_id"] == "ses-gabe-warehouse"]
        self.assertTrue(gabe)
        self.assertEqual(gabe[0]["person_pseudonym"], "anonymous")
        self.assertNotIn(target_label, json.dumps(resp))


class NoCompensationTests(unittest.TestCase):
    def test_display_metadata_cannot_change_ranking(self):
        svc_a, by_a = make_service()
        resp_a = flagship_response(svc_a, by_a)
        mutated = copy.deepcopy(SESSIONS)
        for s in mutated:
            if is_discoverable(s):
                s["presentation"]["topic"] = "swapped"
                s["presentation"]["domain"] = "swapped"
                s["person"]["display_label"] = s["person"]["display_label"].upper()
                if s["consent"]["share_coarse_location"]:
                    s["location"]["region"] = "Nowhere"
        svc_b, by_b = make_service(mutated)
        resp_b = flagship_response(svc_b, by_b)
        key = lambda r: [(m["session_id"], m["mode_classification"], m["scores"])
                         for m in r["matches"]]
        self.assertEqual(key(resp_a), key(resp_b))

    def test_segregation_is_engine_hard_rejection_only(self):
        svc, by_session = make_service()
        resp = flagship_response(svc, by_session)
        self.assertTrue(all(m["hard_rejection"] is None for m in resp["matches"]))
        self.assertTrue(all(m["hard_rejection"] for m in resp["rejected"]))
        self.assertTrue(any(m["session_id"] == "ses-lea-plasma-polarity"
                            for m in resp["rejected"]))

    def test_discovery_sources_contain_no_engine_logic(self):
        for module in ("service.py", "mcp.py", "metadata.py"):
            text = (REPO / "src" / "discovery" / module).read_text()
            for forbidden in ("src.alignment", "src.index.store", "src.fingerprint",
                              "src.scoring", "solve_fgw", "adjudicate(",
                              "sorted(match", "reverse=True"):
                self.assertNotIn(forbidden, text, module)


class ContractTests(unittest.TestCase):
    def test_flagship_gate_useful_matches_with_evidence(self):
        svc, by_session = make_service()
        resp = flagship_response(svc, by_session)
        cluster = [m for m in resp["matches"]
                   if m["display"]["cluster_id"] == "accumulating-intermediary-failure"
                   and m["mode_classification"] == "analogical"]
        self.assertGreaterEqual(len(cluster), 2)
        for m in cluster:
            self.assertGreaterEqual(m["evidence"]["mapped_node_count"], 4)
            self.assertTrue(m["evidence"]["top_correspondences"])
            self.assertTrue(m["evidence"]["preserved_relations"])

    def test_provenance_pins_engine_identity(self):
        svc, by_session = make_service()
        resp = flagship_response(svc, by_session, k=5)
        prov = resp["query"]["provenance"]
        self.assertEqual(prov["verifier_config_hash"],
                         svc.engine.verifier.config_hash)
        self.assertEqual(prov["corpus_snapshot"],
                         svc.engine.candidate_index.corpus_snapshot)
        self.assertEqual(prov["metadata_schema_version"], "resonance-demo-corpus/0.1")

    def test_registry_mirrors_r7_discoverability_exactly(self):
        """Registry has profiles for R7-discoverable sessions and no others."""
        svc, _ = make_service()
        for s in SESSIONS:
            tid = s["thought_dna"]["thought_id"]
            self.assertEqual(svc.registry.discoverable(tid), is_discoverable(s))

    def test_unknown_mode_and_match_id_raise(self):
        svc, by_session = make_service()
        with self.assertRaises(ValueError):
            svc.discover(flagship_query(by_session), mode="semantic")
        with self.assertRaises(ValueError):
            svc.request_intro("nope")

    def test_intro_event_discloses_nothing(self):
        svc, by_session = make_service()
        resp = flagship_response(svc, by_session)
        event = svc.request_intro(resp["matches"][0]["match_id"], "hello")
        self.assertEqual(event["state"], "pending_target_acceptance")
        blob = json.dumps(svc.audit_log())
        self.assertNotIn("hello", blob)
        self.assertNotIn("_target_session", blob)

    def test_determinism(self):
        svc, by_session = make_service()
        q = flagship_query(by_session)
        a = svc.discover(q, mode="analogical", k=15)
        b = svc.discover(q, mode="analogical", k=15)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))


class WireTests(unittest.TestCase):
    def test_discover_tool_over_the_wire_and_r6_tools_intact(self):
        from src.discovery.demo_server import DiscoveryMCPServer, build_service
        from src.discovery.mcp import DiscoveryAdapter, TOOLS
        from src.mcp.adapter import TOOLS as BASE_TOOLS
        self.assertEqual(len(TOOLS), len(BASE_TOOLS) + 1)
        self.assertEqual([t["name"] for t in TOOLS[:len(BASE_TOOLS)]],
                         [t["name"] for t in BASE_TOOLS])
        svc = build_service()
        server = DiscoveryMCPServer(DiscoveryAdapter(svc))
        _, by_session = make_service()
        query = flagship_query(by_session)
        frames = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                  {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                   "params": {"name": "discover_resonance",
                              "arguments": {"thought": query.to_dict(),
                                            "mode": "analogical", "k": 15}}}]
        out = io.StringIO()
        server.serve(io.StringIO("\n".join(json.dumps(f) for f in frames) + "\n"), out)
        body = json.loads(json.loads(out.getvalue().splitlines()[1])
                          ["result"]["content"][0]["text"])
        self.assertGreaterEqual(len(body["matches"]), 4)
        self.assertNotIn("ravi", json.dumps(body).lower())


if __name__ == "__main__":
    unittest.main()
