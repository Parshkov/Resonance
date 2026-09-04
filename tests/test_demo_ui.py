"""R9 visual client: presentation boundary, fidelity, privacy, and parity."""

from __future__ import annotations

import copy
import json
import struct
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from demo.ui.presentation import (  # noqa: E402
    CANONICAL_K,
    CANONICAL_MODE,
    first_contradiction,
    primary_matches,
    remaining_match_count,
    visible_signature,
)
from demo.ui.server import (  # noqa: E402
    DemoHandler,
    REPLAY_FIXTURE,
    load_replay,
    load_replay_bytes,
    public_context,
    verify_sources,
)

# Verified order (engine 0.2): retrieval proposes, verification ranks.
EXPECTED_PRIMARY = [
    "ses-kwame-traffic",
    "ses-noah-org-overload",
    "ses-mei-battery-heat",
    "ses-gabe-warehouse",
]


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.payload = load_replay()

    def test_canonical_four_are_first_eligible_analogies(self):
        selected = primary_matches(self.payload)
        self.assertEqual([row["session_id"] for row in selected], EXPECTED_PRIMARY)
        self.assertTrue(all(row["mode_classification"] == "analogical"
                            for row in selected))
        self.assertTrue(all(row["hard_rejection"] is None for row in selected))

    def test_primary_falls_back_to_other_resonances_when_no_analogues(self):
        # A live person's own thought may resonate directly/approximately
        # (same domain) rather than analogically; the page must still show
        # those in backend order, never negatives or hard rejections.
        mutated = copy.deepcopy(self.payload)
        for row in mutated["matches"]:
            if row["mode_classification"] == "analogical":
                row["mode_classification"] = "approximate"
        selected = primary_matches(mutated)
        self.assertEqual(len(selected), 4)
        self.assertTrue(all(row["mode_classification"] in {"approximate", "complementary"}
                            for row in selected))
        self.assertTrue(all(row["hard_rejection"] is None for row in selected))
        order = [row["session_id"] for row in mutated["matches"]]
        self.assertEqual([row["session_id"] for row in selected],
                         sorted((row["session_id"] for row in selected), key=order.index))
        # analogues still win the slots when they exist, others only fill up
        two = copy.deepcopy(self.payload)
        kept = 0
        for row in two["matches"]:
            if row["mode_classification"] == "analogical":
                kept += 1
                if kept > 2:
                    row["mode_classification"] = "approximate"
        selected = primary_matches(two)
        self.assertEqual([row["mode_classification"] for row in selected][:2], ["analogical", "analogical"])
        self.assertEqual(len(selected), 4)

    def test_backend_order_is_preserved_without_score_or_metadata_ranking(self):
        mutated = copy.deepcopy(self.payload)
        by_id = {row["session_id"]: row for row in mutated["matches"]}
        deliberate_order = [
            "ses-mei-battery-heat",
            "ses-noah-org-overload",
            "ses-gabe-warehouse",
            "ses-kwame-traffic",
        ]
        analogues = [by_id.pop(session_id) for session_id in deliberate_order]
        for index, row in enumerate(analogues):
            row["scores"]["structural"] = index / 10
            row["display"]["topic"] = f"presentation-only-{3 - index}"
            if row["display"].get("location"):
                row["display"]["location"]["lon"] = 170 - index
        mutated["matches"] = analogues + list(by_id.values())
        self.assertEqual(
            [row["session_id"] for row in primary_matches(mutated)],
            deliberate_order,
        )

    def test_scores_classifications_identity_location_and_evidence_are_exact(self):
        selected = primary_matches(self.payload)
        signature = visible_signature(self.payload)
        for source, visible in zip(selected, signature):
            self.assertEqual(visible["match_id"], source["match_id"])
            self.assertEqual(visible["person_pseudonym"], source["person_pseudonym"])
            self.assertEqual(visible["session_id"], source["session_id"])
            self.assertEqual(visible["mode_classification"], source["mode_classification"])
            self.assertEqual(visible["structural"], source["scores"]["structural"])
            self.assertEqual(visible["confidence"], source["confidence"])
            self.assertEqual(visible["display"], source["display"])
            self.assertEqual(visible["evidence"], source["evidence"])

    def test_hidden_rows_fail_closed_in_primary_and_rejected_surfaces(self):
        mutated = copy.deepcopy(self.payload)
        hidden_match = copy.deepcopy(mutated["matches"][1])
        hidden_match["session_id"] = "ses-private-injected"
        hidden_match["display"]["share_state"] = "hidden"
        mutated["matches"].insert(0, hidden_match)
        hidden_rejected = copy.deepcopy(mutated["rejected"][0])
        hidden_rejected["session_id"] = "ses-private-rejected"
        hidden_rejected["display"]["share_state"] = "hidden"
        mutated["rejected"].insert(0, hidden_rejected)
        self.assertNotIn(
            "ses-private-injected",
            [row["session_id"] for row in primary_matches(mutated)],
        )
        self.assertNotEqual(first_contradiction(mutated)["session_id"],
                            "ses-private-rejected")

    def test_hard_rejection_is_never_a_primary_resonance(self):
        mutated = copy.deepcopy(self.payload)
        rejected = copy.deepcopy(mutated["rejected"][0])
        mutated["matches"].insert(0, rejected)
        self.assertNotIn(
            rejected["session_id"],
            [row["session_id"] for row in primary_matches(mutated)],
        )
        contradiction = first_contradiction(mutated)
        self.assertIsNotNone(contradiction)
        self.assertTrue(contradiction["hard_rejection"])

    def test_other_returned_rows_remain_counted(self):
        self.assertEqual(remaining_match_count(self.payload), 6)


class SourceAndBoundaryTests(unittest.TestCase):
    def test_replay_is_the_genuine_accepted_fixture_byte_for_byte(self):
        self.assertEqual(REPLAY_FIXTURE,
                         REPO / "src/discovery/fixtures/example_response.json")
        self.assertEqual(load_replay_bytes(), REPLAY_FIXTURE.read_bytes())

    def test_live_and_replay_have_exact_visible_parity(self):
        report = verify_sources()
        self.assertTrue(report["live_replay_visible_equal"])
        self.assertEqual(report["pinned_request"],
                         {"mode": CANONICAL_MODE, "k": CANONICAL_K})
        self.assertEqual(report["visible_match_count"], 4)
        self.assertEqual(report["visible_session_ids"], EXPECTED_PRIMARY)
        self.assertEqual(report["live_corpus_snapshot"],
                         report["replay_corpus_snapshot"])

    def test_public_context_contains_only_consented_presentation_fields(self):
        context = public_context()
        self.assertTrue(context["consent"]["shared_with_resonance"])
        self.assertEqual(context["pinned_request"],
                         {"mode": "analogical", "k": 15})
        self.assertEqual(context["location"]["kind"], "synthetic_coarse")
        self.assertEqual(context["location"]["precision"], "city")
        self.assertNotIn("person", context)
        self.assertNotIn("person_pseudonym", context)
        self.assertNotIn("email", json.dumps(context).lower())

    def test_ui_sources_do_not_import_matching_internals_or_sort_results(self):
        ui = REPO / "demo/ui"
        source_files = [ui / "presentation.py", ui / "server.py", ui / "app.mjs"]
        forbidden_imports = (
            "src.alignment", "src.engine", "src.fingerprint", "src.index",
            "src.retrieval", "src.scoring", "src.verifier",
        )
        for path in source_files:
            source = path.read_text(encoding="utf-8")
            for forbidden in forbidden_imports:
                self.assertNotIn(forbidden, source, path.name)
        frontend = (ui / "app.mjs").read_text(encoding="utf-8")
        self.assertNotIn(".sort(", frontend)
        self.assertNotIn("Math.random", frontend)
        self.assertNotIn("request_intro", frontend)
        self.assertIn('const CANONICAL_MODE = "analogical"', frontend)
        self.assertIn("const CANONICAL_K = 15", frontend)
        self.assertIn("dataset.backendScore = String(match.scores.structural)", frontend)

    def test_static_http_surface_serves_fixture_and_security_headers(self):
        class QuietHandler(DemoHandler):
            def log_message(self, format, *args):  # noqa: A002
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        try:
            with urlopen(f"http://{host}:{port}/", timeout=5) as response:
                body = response.read().decode("utf-8")
                self.assertIn("Resonance map", body)
                self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
            with urlopen(f"http://{host}:{port}/api/discover?source=replay", timeout=5) as response:
                self.assertEqual(response.read(), load_replay_bytes())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_recording_artifact_is_exactly_1920_by_1080(self):
        artifact = REPO / "demo/ui/artifacts/canonical-1920x1080.jpg"
        blob = artifact.read_bytes()
        self.assertEqual(blob[:2], b"\xff\xd8")
        width = height = None
        offset = 2
        start_of_frame = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
        while offset + 8 < len(blob):
            if blob[offset] != 0xFF:
                offset += 1
                continue
            while offset < len(blob) and blob[offset] == 0xFF:
                offset += 1
            marker = blob[offset]
            offset += 1
            if marker in {0x01, 0xD8, 0xD9}:
                continue
            segment_length = struct.unpack(">H", blob[offset:offset + 2])[0]
            if marker in start_of_frame:
                height = struct.unpack(">H", blob[offset + 3:offset + 5])[0]
                width = struct.unpack(">H", blob[offset + 5:offset + 7])[0]
                break
            offset += segment_length
        self.assertEqual((width, height), (1920, 1080))


if __name__ == "__main__":
    unittest.main()
