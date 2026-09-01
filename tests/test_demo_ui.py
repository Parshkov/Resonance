"""R9 visual demo: presentation-only projection over accepted R8 payloads."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from demo.ui.contract import CONTRACT_VERSION, FEATURE_LIMIT, PINNED_K, PINNED_MODE
from demo.ui.poster import render_svg
from demo.ui.view_model import featured_session_ids, project


FIXTURE = REPO / "src/discovery/fixtures/example_response.json"
UI = REPO / "demo" / "ui"
FORBIDDEN = (
    "src.alignment",
    "src.index",
    "src.fingerprint",
    "src.scoring",
    "solve_fgw",
    "adjudicate(",
    "sorted(",
    "reverse=True",
    "semantic-similarity",
    "embed",
)


def replay_view():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return payload, project(payload, source="replay")


class ProjectionTests(unittest.TestCase):
    def test_featured_cards_are_first_analogical_backend_rows(self):
        payload, view = replay_view()
        analogical = [
            m["session_id"]
            for m in payload["matches"]
            if m["mode_classification"] == "analogical" and m["hard_rejection"] is None
        ][:FEATURE_LIMIT]
        self.assertEqual(featured_session_ids(view), analogical)
        self.assertEqual(
            analogical,
            [
                "ses-gabe-warehouse",
                "ses-kwame-traffic",
                "ses-mei-battery-heat",
                "ses-noah-org-overload",
            ],
        )
        self.assertEqual(len(view["featured"]), 4)

    def test_card_values_are_copied_not_recomputed(self):
        payload, view = replay_view()
        by_id = {m["session_id"]: m for m in payload["matches"]}
        for card in view["featured"]:
            src = by_id[card["session_id"]]
            self.assertEqual(card["scores"], src["scores"])
            self.assertEqual(card["structural"], src["scores"]["structural"])
            self.assertEqual(card["mode_classification"], src["mode_classification"])
            self.assertEqual(card["person_pseudonym"], src["person_pseudonym"])
            self.assertEqual(card["evidence"], src["evidence"])

    def test_featured_and_other_preserve_backend_subsequence_order(self):
        payload, view = replay_view()
        backend = [m["session_id"] for m in payload["matches"]]
        featured = featured_session_ids(view)
        other = [c["session_id"] for c in view["other_matches"]]
        self.assertEqual(featured, [sid for sid in backend if sid in featured])
        self.assertEqual(other, [sid for sid in backend if sid in other])
        self.assertEqual(set(featured + other), set(backend))

    def test_hidden_sessions_cannot_appear(self):
        _, view = replay_view()
        blob = json.dumps(view).lower()
        for token in ("ravi", "nico", "irrigation", "tracing-private"):
            self.assertNotIn(token, blob)

    def test_contradictions_stay_out_of_featured_strip(self):
        payload, view = replay_view()
        rejected_ids = {m["session_id"] for m in payload["rejected"]}
        self.assertTrue(rejected_ids)
        self.assertTrue(all(c["session_id"] not in rejected_ids for c in view["featured"]))
        self.assertEqual(
            [c["session_id"] for c in view["contradictions"]],
            [m["session_id"] for m in payload["rejected"]],
        )
        self.assertTrue(all(c["hard_rejection"] for c in view["contradictions"]))

    def test_intro_is_explicitly_unwired(self):
        _, view = replay_view()
        self.assertEqual(view["intro_status"], "not_wired_r8_v0.1")
        self.assertTrue(all(c["intro_status"] == "not_wired_r8_v0.1" for c in view["featured"]))

    def test_pinned_contract_and_provenance(self):
        payload, view = replay_view()
        self.assertEqual(payload["contract_version"], CONTRACT_VERSION)
        self.assertEqual(view["pinned"], {"mode": PINNED_MODE, "k": PINNED_K, "contract": CONTRACT_VERSION})
        self.assertEqual(
            view["provenance"]["verifier_config_hash"],
            payload["query"]["provenance"]["verifier_config_hash"],
        )


class BoundaryTests(unittest.TestCase):
    def test_ui_sources_contain_no_matching_engine(self):
        scanned = list((UI / "static").glob("*")) + [
            UI / "view_model.py",
            UI / "contract.py",
            UI / "poster.py",
            UI / "serve.py",
        ]
        for path in scanned:
            text = path.read_text(encoding="utf-8")
            for token in FORBIDDEN:
                self.assertNotIn(token, text, f"{path.name} contains {token}")


class LiveReplayParityTests(unittest.TestCase):
    def test_live_mcp_featured_cards_match_replay_fixture(self):
        from demo.ui.live import discover_live
        replay_payload, replay = replay_view()
        live_payload = discover_live(REPO)
        live = project(live_payload, source="live")
        self.assertEqual(featured_session_ids(live), featured_session_ids(replay))
        self.assertEqual(
            [c["scores"] for c in live["featured"]],
            [c["scores"] for c in replay["featured"]],
        )
        self.assertEqual(live_payload["contract_version"], replay_payload["contract_version"])
        self.assertEqual(
            live_payload["query"]["provenance"]["verifier_config_hash"],
            replay_payload["query"]["provenance"]["verifier_config_hash"],
        )


class PosterTests(unittest.TestCase):
    def test_canonical_poster_is_deterministic(self):
        _, view = replay_view()
        svg = render_svg(view)
        path = UI / "fixtures" / "canonical_poster.svg"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(svg, encoding="utf-8")
        self.assertEqual(svg, path.read_text(encoding="utf-8"))
        self.assertIn("Gabe S.", svg)
        self.assertIn("1920", svg)


if __name__ == "__main__":
    unittest.main()
