"""R13B acceptance battery: rich results, deterministic visuals, MCP packaging."""

from __future__ import annotations

import json
import unittest

from src.identity.models import ConsentChoices
from src.ingestion.service import ShareIntent
from src.product import ProductError, StaleResultError
from src.product.rich import (
    RICH_RESULT_CONTRACT,
    RICH_RESULT_SCHEMA,
    build_rich_result,
    render_map_svg,
    render_structure_svg,
    svg_sha256,
    to_mcp_content,
)
from tests.test_product_live import (
    ORIGIN,
    PRES,
    QUERY_DNA,
    build_stack,
    location,
    r7_dna,
    share_thought,
)

# Pinned by running the canonical seeded render at authoring time; the seed
# corpus, engine, aggregation ordering, and renderer are all deterministic,
# so any drift here is a real visual regression.
#
# Moved once, on 2026-09-05, and the pin is what caught it: the drawings were
# hard-coded dark and were repainted in the product's own light palette. A
# deliberate change to how the map looks is the only reason to touch this
# line, and it should be uncomfortable to touch.
CANONICAL_MAP_SHA256 = "6ce8418f1314cb79138e9ef1308bf2ac92bdd221788179419baac1dcdce3b2d3"


def _order_key(rows):
    return [(r["session_id"], r["mode_classification"],
             json.dumps(r["scores"], sort_keys=True),
             json.dumps(r["evidence"], sort_keys=True)) for r in rows]


class RichResultShapeTests(unittest.TestCase):
    def setUp(self):
        self.live, self.identity, self.product = build_stack()
        self.alice = self.product.register("Alice")
        self.bob = self.product.register("Bob")
        self.a_session, _ = share_thought(
            self.product, self.alice, r7_dna("ses-gabe-warehouse", "thought-alice"),
            loc=location("R"),
            intent=ShareIntent(share_display_profile=True,
                               share_coarse_location=True,
                               receive_intro_requests=True))
        self.b_session, _ = share_thought(
            self.product, self.bob, r7_dna(QUERY_DNA, "thought-bob-query"),
            loc=location("R", lat=55.9, lon=37.7),
            intent=ShareIntent(share_display_profile=True,
                               share_coarse_location=True))

    def test_rich_result_schema_fields_and_intro_state(self):
        rich = self.product.rich_discover(self.bob.access_token, self.b_session, k=8)
        self.assertEqual(rich["contract_version"], RICH_RESULT_CONTRACT)
        for field in RICH_RESULT_SCHEMA["required"]:
            self.assertIn(field, rich)
        self.assertEqual(rich["query_ref"]["session_id"], self.b_session)
        self.assertTrue(rich["provenance"])
        row = next(m for m in rich["matches"] if m["session_id"] == self.a_session)
        for field in RICH_RESULT_SCHEMA["properties"]["matches"]["items"]["required"]:
            self.assertIn(field, row)
        self.assertEqual(row["intro_state"], "available")
        self.assertEqual(row["ui_ref"],
                         f"/#match={rich['result_id']}:{self.a_session}")
        other = next(m for m in rich["matches"]
                     if m["session_id"] != self.a_session)
        self.assertIn(other["intro_state"], {"available", "unavailable"})

    def test_rows_pass_through_order_and_scores_unchanged(self):
        plain = self.product.discover(self.bob.access_token, self.b_session, k=20)
        rich = self.product.rich_result(self.bob.access_token, plain["result_id"])
        self.assertEqual(_order_key(plain["matches"]), _order_key(rich["matches"]))

    def test_three_surfaces_identical_ids_order_scores_evidence(self):
        plain = self.product.discover(self.bob.access_token, self.b_session, k=20)
        rich = self.product.rich_discover(self.bob.access_token, self.b_session, k=20)
        mcp = self.product.mcp_rich_discover(self.bob.access_token,
                                             self.b_session, k=20)
        self.assertEqual(_order_key(plain["matches"]),
                         _order_key(rich["matches"]))
        self.assertEqual(_order_key(rich["matches"]),
                         _order_key(mcp["structuredContent"]["matches"]))

    def test_mcp_packaging_rich_and_imageless(self):
        mcp = self.product.mcp_rich_discover(self.bob.access_token,
                                             self.b_session, k=8)
        self.assertEqual(mcp["outputSchema"]["title"], RICH_RESULT_CONTRACT)
        kinds = [block["type"] for block in mcp["content"]]
        self.assertIn("text", kinds)
        self.assertIn("resource", kinds)
        resource = next(b for b in mcp["content"] if b["type"] == "resource")
        self.assertEqual(resource["resource"]["mimeType"], "image/svg+xml")
        self.assertTrue(resource["resource"]["text"].startswith("<svg"))
        plain = self.product.mcp_rich_discover(self.bob.access_token,
                                               self.b_session, k=8,
                                               include_visual=False)
        self.assertEqual([b["type"] for b in plain["content"]], ["text"])
        self.assertTrue(plain["structuredContent"]["matches"])
        self.assertIn("resonance match", plain["content"][0]["text"])

    def test_image_contains_only_authorized_matches_and_no_ids(self):
        rich = self.product.rich_discover(self.bob.access_token, self.b_session, k=20)
        svg = render_map_svg(rich)
        allowed = {m["person_pseudonym"] for m in rich["matches"]}
        self.assertIn("Alice", svg)
        self.assertTrue(allowed.issuperset(
            {"Alice"} | {p for p in allowed if p in svg}))
        for needle in ("ses-", "person-", "thought-", "result-", "token"):
            self.assertNotIn(needle, svg)
        self.assertIn("presentation-only", svg)

    def test_block_removes_row_from_stored_rich_and_regenerated_image(self):
        plain = self.product.discover(self.bob.access_token, self.b_session, k=20)
        rid = plain["result_id"]
        self.assertIn("Alice", self.product.visual_map(self.bob.access_token, rid))
        self.identity.policy_source.block(self.bob.user_id, self.alice.user_id)
        rich_after = self.product.rich_result(self.bob.access_token, rid)
        self.assertNotIn(self.a_session,
                         [m["session_id"] for m in rich_after["matches"]])
        self.assertNotIn("Alice",
                         self.product.visual_map(self.bob.access_token, rid))

    def test_revoke_removes_from_json_and_regenerated_image(self):
        plain = self.product.discover(self.bob.access_token, self.b_session, k=20)
        rid = plain["result_id"]
        self.product.revoke_session(
            self.alice.access_token, self.a_session, confirmed=True,
            csrf_token=self.alice.csrf_token, cookie_authenticated=True,
            origin=ORIGIN, client_id="manual-ui")
        with self.assertRaises(StaleResultError):
            self.product.visual_map(self.bob.access_token, rid)
        fresh = self.product.rich_discover(self.bob.access_token,
                                           self.b_session, k=20)
        self.assertNotIn(self.a_session,
                         [m["session_id"] for m in fresh["matches"]])
        self.assertNotIn("Alice", render_map_svg(fresh))

    def test_visuals_not_reusable_by_second_user(self):
        plain = self.product.discover(self.bob.access_token, self.b_session, k=8)
        with self.assertRaises(ProductError):
            self.product.visual_map(self.alice.access_token, plain["result_id"])
        with self.assertRaises(ProductError):
            self.product.rich_result(self.alice.access_token, plain["result_id"])

    def test_metadata_change_cannot_change_rich_ordering_or_scores(self):
        before = self.product.rich_discover(self.bob.access_token,
                                            self.b_session, k=20)
        self.product.update_metadata(
            self.alice.access_token, self.a_session,
            location=location("Z", lat=-10.0, lon=80.0),
            presentation={"domain": "mut", "topic": "mut", "cluster_id": "mut"},
            csrf_token=self.alice.csrf_token, cookie_authenticated=True,
            origin=ORIGIN, client_id="manual-ui")
        after = self.product.rich_discover(self.bob.access_token,
                                           self.b_session, k=20)
        strip = lambda rows: [(r["session_id"], r["mode_classification"],
                               json.dumps(r["scores"], sort_keys=True))
                              for r in rows]
        self.assertEqual(strip(before["matches"]), strip(after["matches"]))

    def test_structure_diagram_renders_evidence_only(self):
        plain = self.product.discover(self.bob.access_token, self.b_session, k=8)
        svg = self.product.visual_structure(self.bob.access_token,
                                            plain["result_id"], self.a_session)
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("preserved relations", svg)
        for needle in ("ses-", "person-", "result-"):
            self.assertNotIn(needle, svg)


class DeterministicVisualTests(unittest.TestCase):
    def test_canonical_seeded_map_is_deterministic(self):
        def canonical_svg():
            live, identity, product = build_stack()
            viewer = product.register("Viewer")
            q_session, _ = share_thought(
                product, viewer, r7_dna(QUERY_DNA, "thought-canonical-query"))
            rich = product.rich_discover(viewer.access_token, q_session, k=20)
            return render_map_svg(rich)

        first, second = canonical_svg(), canonical_svg()
        self.assertEqual(first, second)
        digest = svg_sha256(first)
        if CANONICAL_MAP_SHA256 == "__PINNED_AT_AUTHORING__":
            print(f"\n[pin-me] canonical map sha256: {digest}")
        else:
            self.assertEqual(digest, CANONICAL_MAP_SHA256)


if __name__ == "__main__":
    unittest.main()
