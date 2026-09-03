"""R13 acceptance battery: live product boundary over the accepted layers.

Covers the #85 contract verbatim (A-shares/B-discovers, restart survival,
revocation removal, metadata permutation invariance, pilot-scale latency,
R9-renderable response shape, WebMCP/manual parity) plus the product-boundary
regressions from the R13 readiness note: viewer-relative block filtering,
result_id staleness on consent transitions, k-anonymous aggregation, and
presentation-only distance context.

Fixtures reuse the accepted R7 corpus Thought DNA (diverse 10-node causal
structures with known resonance clusters). Degenerate low-node clone corpora
are a known retrieval pathology of synthetic fixtures, not of the product.
"""

from __future__ import annotations

import copy
import json
import tempfile
import time
import unittest
from pathlib import Path

from demo.corpus.discovery import load_sessions
from src.identity import IdentityService, R11IdentityBackend
from src.ingestion import (
    IdentityIngestionService,
    ManualIngestionAdapter,
    WebMCPIngestionAdapter,
)
from src.ingestion.service import ShareIntent
from src.persistence import LiveCorpusService, SQLiteRepository
from src.persistence.seed import seed_r7
from src.product import (
    LIVE_PRODUCT_CONTRACT,
    LiveProductService,
    ProductError,
    StaleResultError,
)

ORIGIN = "https://app.resonance.example"
SECRET = b"r13-live-product-secret-32bytes!"
PRES = {"domain": "engineering", "topic": "thermal", "cluster_id": "c1"}

_R7 = {s["session_id"]: s for s in load_sessions()}
QUERY_DNA = "ses-aria-plasma-lens"        # accepted flagship query
RESONANT = ("ses-gabe-warehouse", "ses-mei-battery-heat",
            "ses-noah-org-overload", "ses-diego-chiller")


def r7_dna(source_session: str, new_thought_id: str) -> dict:
    """Deep-copied accepted R7 Thought DNA under a fresh unique thought_id."""
    dna = copy.deepcopy(dict(_R7[source_session]["thought_dna"]))
    dna["thought_id"] = new_thought_id
    return dna


def location(region: str = "R", lat: float = 55.8, lon: float = 37.6) -> dict:
    return {"kind": "synthetic_coarse", "region": region, "city": f"city-{region}",
            "lat": lat, "lon": lon, "precision": "city"}


def build_stack(db_path=":memory:", *, seed=True):
    """Live stack over the seeded baseline platform.

    The pilot ships with the accepted R7 seed corpus as ambient discoverable
    content (clearly labeled `record_kind=synthetic`); live user sessions are
    layered on top. This also gives the accepted MULTI retrieval the
    distributional mass its discriminativeness weighting assumes — a
    cold-start corpus of N<=2 near-duplicates is a documented small-N
    weakness of the frozen retrieval layer, not of this product boundary.
    """
    live = LiveCorpusService(SQLiteRepository(db_path))
    if seed:
        seed_r7(live)
    identity = IdentityService(
        R11IdentityBackend(live), allowed_origins=frozenset({ORIGIN})
    )
    product = LiveProductService(identity, confirmation_secret=SECRET)
    return live, identity, product


def share_thought(product, creds, thought, *, loc=None, intent=None,
                  presentation=PRES):
    """Full accepted journey: R12C prepare -> preview -> explicit share."""
    prepared = product.prepare_structured(
        creds.access_token, thought,
        presentation=dict(presentation),
        coarse_location=dict(loc) if loc else None,
        intent=intent,
        csrf_token=creds.csrf_token, cookie_authenticated=True,
        origin=ORIGIN, client_id="manual-ui",
    )
    preview = product.preview(creds.access_token, prepared["draft_id"],
                              client_id="manual-ui")
    receipt = product.share_prepared(
        creds.access_token, prepared["draft_id"],
        confirmation_token=preview["confirmation_token"], confirmed=True,
        csrf_token=creds.csrf_token, cookie_authenticated=True,
        origin=ORIGIN, client_id="manual-ui",
    )
    return prepared["session_id"], receipt


class TwoUserJourneyTests(unittest.TestCase):
    def setUp(self):
        self.live, self.identity, self.product = build_stack()
        self.alice = self.product.register("Alice")
        self.bob = self.product.register("Bob")

    def _bob_query_session(self):
        session_id, _ = share_thought(
            self.product, self.bob, r7_dna(QUERY_DNA, "thought-bob-query"),
            loc=location("R", lat=55.9, lon=37.7))
        return session_id

    def test_a_shares_b_discovers_when_structurally_resonant(self):
        a_session, receipt = share_thought(
            self.product, self.alice, r7_dna("ses-gabe-warehouse", "thought-alice"),
            loc=location("R"),
            intent=ShareIntent(share_display_profile=True,
                               share_coarse_location=True),
        )
        self.assertTrue(receipt["discoverable"])
        b_session = self._bob_query_session()
        response = self.product.discover(self.bob.access_token, b_session, k=8)
        self.assertEqual(response["contract_version"], LIVE_PRODUCT_CONTRACT)
        self.assertEqual(response["source"], "live")
        found = [m["session_id"] for m in response["matches"]]
        self.assertIn(a_session, found)
        self.assertTrue(response["freshness"]["index_current"])
        self.assertTrue(response["result_id"].startswith("result-"))
        row = next(m for m in response["matches"] if m["session_id"] == a_session)
        self.assertEqual(row["person_pseudonym"], "Alice")
        self.assertEqual(row["display"]["distance_context"]["bucket"], "near")
        self.assertTrue(row["display"]["distance_context"]["presentation_only"])

    def test_get_match_is_bound_to_stored_result_and_fails_closed_on_change(self):
        a_session, _ = share_thought(
            self.product, self.alice, r7_dna("ses-gabe-warehouse", "thought-alice"))
        b_session = self._bob_query_session()
        response = self.product.discover(self.bob.access_token, b_session)
        rid = response["result_id"]
        evidence = self.product.get_match(self.bob.access_token, rid, a_session)
        self.assertEqual(evidence["match"]["session_id"], a_session)
        self.assertIn("top_correspondences", evidence["match"]["evidence"])
        # owner revokes -> durable generation moves -> stored result is dead
        self.product.revoke_session(
            self.alice.access_token, a_session, confirmed=True,
            csrf_token=self.alice.csrf_token, cookie_authenticated=True,
            origin=ORIGIN, client_id="manual-ui",
        )
        with self.assertRaises(StaleResultError):
            self.product.get_match(self.bob.access_token, rid, a_session)
        fresh = self.product.discover(self.bob.access_token, b_session)
        self.assertNotIn(a_session, [m["session_id"] for m in fresh["matches"]])

    def test_foreign_result_id_and_foreign_session_are_refused(self):
        b_session = self._bob_query_session()
        response = self.product.discover(self.bob.access_token, b_session)
        with self.assertRaises(ProductError):
            self.product.get_match(self.alice.access_token,
                                   response["result_id"], b_session)
        with self.assertRaises(Exception):
            self.product.discover(self.alice.access_token, b_session)

    def test_blocked_owner_rows_are_removed_for_that_viewer_only(self):
        a_session, _ = share_thought(
            self.product, self.alice, r7_dna("ses-gabe-warehouse", "thought-alice"))
        b_session = self._bob_query_session()
        carol = self.product.register("Carol")
        c_session, _ = share_thought(
            self.product, carol, r7_dna(QUERY_DNA, "thought-carol-query"))
        self.identity.policy_source.block(self.bob.user_id, self.alice.user_id)
        for_bob = self.product.discover(self.bob.access_token, b_session)
        self.assertNotIn(a_session, [m["session_id"] for m in for_bob["matches"]])
        self.assertGreaterEqual(for_bob["blocked_rows_removed"], 1)
        for_carol = self.product.discover(carol.access_token, c_session)
        self.assertIn(a_session, [m["session_id"] for m in for_carol["matches"]])

    def test_hidden_display_profile_is_anonymous_and_location_absent(self):
        a_session, _ = share_thought(
            self.product, self.alice, r7_dna("ses-gabe-warehouse", "thought-alice"),
            loc=location("R"),
            intent=ShareIntent(share_display_profile=False,
                               share_coarse_location=False),
        )
        b_session = self._bob_query_session()
        response = self.product.discover(self.bob.access_token, b_session)
        row = next(m for m in response["matches"] if m["session_id"] == a_session)
        self.assertEqual(row["person_pseudonym"], "anonymous")
        self.assertNotIn("location", row["display"])
        self.assertNotIn("distance_context", row["display"])


class PresentationInvariantTests(unittest.TestCase):
    def setUp(self):
        self.live, self.identity, self.product = build_stack()
        self.viewer = self.product.register("Viewer")
        self.owners = []
        for i, source in enumerate(RESONANT):
            creds = self.product.register(f"Owner{i}")
            session_id, _ = share_thought(
                self.product, creds, r7_dna(source, f"thought-owner-{i}"),
                loc=location("R", lat=10.0 + i, lon=20.0 + i),
                intent=ShareIntent(share_display_profile=True,
                                   share_coarse_location=True),
            )
            self.owners.append((creds, session_id))
        self.query_session, _ = share_thought(
            self.product, self.viewer, r7_dna(QUERY_DNA, "thought-viewer-query"))

    def _key(self, response):
        return [(m["session_id"], m["mode_classification"],
                 json.dumps(m["scores"], sort_keys=True))
                for m in response["matches"]]

    def test_metadata_permutation_cannot_change_order_or_scores(self):
        before = self._key(self.product.discover(
            self.viewer.access_token, self.query_session, k=20))
        self.assertTrue(before)
        for creds, session_id in self.owners:
            self.product.update_metadata(
                creds.access_token, session_id,
                location=location("Z", lat=-30.0, lon=90.0),
                presentation={"domain": "mut", "topic": "mut", "cluster_id": "mut"},
                csrf_token=creds.csrf_token, cookie_authenticated=True,
                origin=ORIGIN, client_id="manual-ui",
            )
        after = self._key(self.product.discover(
            self.viewer.access_token, self.query_session, k=20))
        self.assertEqual(before, after)

    def test_aggregation_is_k_anonymous(self):
        # region R holds several consented shares -> visible; a lone region -> suppressed
        lone = self.product.register("Lone")
        share_thought(
            self.product, lone, r7_dna("ses-theo-plasma-granular", "thought-lone"),
            loc=location("Q"),
            intent=ShareIntent(share_display_profile=True,
                               share_coarse_location=True),
        )
        response = self.product.discover(
            self.viewer.access_token, self.query_session, k=20)
        buckets = {b["bucket_id"]: b["count"]
                   for b in response["aggregation"]["buckets"]}
        self.assertIn("R", buckets)
        self.assertGreaterEqual(buckets["R"], 3)
        self.assertNotIn("Q", buckets)
        self.assertGreaterEqual(response["aggregation"]["suppressed_bucket_count"], 1)
        self.assertEqual(response["aggregation"]["anti_inference_minimum"], 3)
        self.assertIn("presentation-only", response["location_note"])

    def test_r9_renderable_response_shape(self):
        response = self.product.discover(
            self.viewer.access_token, self.query_session, k=20)
        self.assertTrue(response["matches"])
        row = response["matches"][0]
        for field in ("match_id", "person_pseudonym", "session_id",
                      "mode_classification", "hard_rejection", "scores",
                      "confidence", "evidence", "display"):
            self.assertIn(field, row)
        for score in ("structural", "semantic", "r_direct", "y_systematicity",
                      "coverage_containment", "contradiction", "h_sign_conflict"):
            self.assertIn(score, row["scores"])
        for field in ("mapped_node_count", "preserved_relation_count",
                      "top_correspondences", "preserved_relations"):
            self.assertIn(field, row["evidence"])
        for field in ("cluster_id", "topic", "domain", "share_state"):
            self.assertIn(field, row["display"])
        self.assertIn("buckets", response["aggregation"])
        self.assertIn("query", response)
        self.assertIn("freshness", response)


class DurabilityAndParityTests(unittest.TestCase):
    def test_new_session_survives_service_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "live.db"
            live, identity, product = build_stack(db)
            alice = product.register("Alice")
            a_session, _ = share_thought(
                product, alice, r7_dna("ses-gabe-warehouse", "thought-alice"))
            bob = product.register("Bob")
            b_session, _ = share_thought(
                product, bob, r7_dna(QUERY_DNA, "thought-bob-query"))
            live.repo.close()

            live2, identity2, product2 = build_stack(db)
            response = product2.discover(bob.access_token, b_session)
            self.assertIn(a_session,
                          [m["session_id"] for m in response["matches"]])
            self.assertTrue(product2.state(bob.access_token)["owned_sessions"])
            live2.repo.close()

    def test_webmcp_and_manual_paths_produce_identical_product_state(self):
        live, identity, product = build_stack()
        manual = ManualIngestionAdapter(product.ingestion, request_origin=ORIGIN)
        webmcp = WebMCPIngestionAdapter(product.ingestion, request_origin=ORIGIN)
        m_user = product.register("Manual")
        w_user = product.register("Web")

        def journey(adapter, creds, source, thought_id):
            prepared = adapter.prepare_structured(
                creds.access_token, r7_dna(source, thought_id),
                presentation=dict(PRES), csrf_token=creds.csrf_token)
            preview = adapter.preview(creds.access_token, prepared["draft_id"])
            adapter.share_prepared(
                creds.access_token, prepared["draft_id"],
                confirmation_token=preview["confirmation_token"],
                confirmed=True, csrf_token=creds.csrf_token)
            return prepared["session_id"]

        m_session = journey(manual, m_user, QUERY_DNA, "thought-manual")
        w_session = journey(webmcp, w_user, "ses-gabe-warehouse", "thought-web")

        def state_key(creds, session_id):
            row = next(r for r in product.owned_sessions(creds.access_token)
                       if r["session_id"] == session_id)
            return (row["share_state"],
                    json.dumps(row["consent_choices"], sort_keys=True))

        self.assertEqual(state_key(m_user, m_session),
                         state_key(w_user, w_session))
        response = product.discover(m_user.access_token, m_session, k=20)
        self.assertIn(w_session, [m["session_id"] for m in response["matches"]])


class PilotScaleLatencyTests(unittest.TestCase):
    def test_100_session_corpus_returns_usable_latency(self):
        live, identity, product = build_stack()
        sources = list(_R7)
        count = 0
        for i in range(100):
            source = sources[i % len(sources)]
            user_id = f"person-pilot-{i:04d}"
            live.create_user(user_id, display_label=f"Pilot {i}", rebuild=False)
            live.create_session(
                session_id=f"ses-pilot-{i:04d}",
                user_id=user_id,
                thought_dna=r7_dna(source, f"thought-pilot-{i:04d}"),
                consent={"share_enabled": True, "share_thought_dna": True,
                         "share_coarse_location": True,
                         "share_display_profile": True},
                location=location("R", lat=10.0 + (i % 40), lon=20.0 + (i % 40)),
                presentation=dict(PRES),
                rebuild=False,
            )
            count += 1
        live.rebuild_index()
        self.assertGreaterEqual(live.health().discoverable, 100)
        viewer = product.register("Viewer")
        q_session, _ = share_thought(
            product, viewer, r7_dna(QUERY_DNA, "thought-viewer-query"))
        started = time.monotonic()
        response = product.discover(viewer.access_token, q_session, k=8)
        elapsed = time.monotonic() - started
        self.assertTrue(response["matches"])
        self.assertLess(elapsed, 20.0,
                        f"discover took {elapsed:.2f}s on 100-session corpus")
        print(f"\n[latency] discover over {count}+1 sessions: {elapsed:.2f}s")


class BoundaryHygieneTests(unittest.TestCase):
    def test_product_module_implements_no_matching_or_scoring(self):
        source = Path("src/product/service.py").read_text(encoding="utf-8")
        for forbidden in ("fgw", "rrwm", "hungarian", "structural_score",
                          "cosine", "embedding"):
            self.assertNotIn(forbidden, source.lower())

    def test_state_reports_live_mode_and_freshness(self):
        live, identity, product = build_stack()
        creds = product.register("Solo")
        state = product.state(creds.access_token)
        self.assertEqual(state["mode"], "live")
        self.assertIn("db_generation", state["freshness"])
        self.assertIn("index_current", state["freshness"])


if __name__ == "__main__":
    unittest.main()
