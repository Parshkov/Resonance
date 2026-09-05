"""The map of where people are, on the site: `/api/geo` and `demo/ui/geo.mjs`.

The privacy design is the point of this surface, so each rule gets a test
that would fail if it were quietly relaxed: a place appears only with that
person's consent and only rounded; a person without one is named rather than
dropped; a region below the anti-inference minimum stays uncounted; and
nothing a person reads is an identifier or a raw float.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.product.server import build_runtime
from src.product.web_server import serve

REPO = Path(__file__).resolve().parents[1]
UI_DIR = REPO / "demo" / "ui"

SHAPE = {
    "topic": "Rework after skipped review", "domain": "engineering",
    "nodes": [{"id": "n0", "label": "pressure to ship", "role": "problem"},
              {"id": "n1", "label": "skipped review", "role": "mechanism"},
              {"id": "n2", "label": "rework", "role": "outcome"},
              {"id": "n3", "label": "jittered backoff", "role": "method"}],
    "relations": [{"source": "n0", "target": "n1", "type": "causes"},
                  {"source": "n1", "target": "n2", "type": "causes"},
                  {"source": "n3", "target": "n2", "type": "prevents"}],
}


class Client:
    def __init__(self, base: str):
        self.base = base
        self.cookie = None
        self.csrf = None

    def request(self, method: str, path: str, body=None):
        headers = {"Content-Type": "application/json", "Origin": self.base}
        if self.cookie:
            headers["Cookie"] = self.cookie
        if self.csrf:
            headers["X-Resonance-CSRF"] = self.csrf
        data = json.dumps(body).encode() if body is not None else None
        req = Request(self.base + path, data=data, headers=headers, method=method)
        with urlopen(req, timeout=15) as response:
            set_cookie = response.headers.get("Set-Cookie")
            if set_cookie:
                morsel = SimpleCookie(set_cookie).get("resonance_token")
                if morsel is not None:
                    self.cookie = f"resonance_token={morsel.value}"
            return response.status, json.loads(response.read().decode())

    def guest(self):
        _, payload = self.request("POST", "/api/product/guest", {})
        self.csrf = payload["csrf_token"]
        return payload

    def share(self, name: str, location=None) -> str:
        """Prepare, preview and share the common shape; returns the session id."""
        body = {"request_id": f"{name}-prepare", "authorship": "their_own_words",
                "thought": SHAPE}
        if location is not None:
            body["coarse_location"] = location
        self.request("POST", "/api/webmcp/prepare", body)
        _, preview = self.request("GET", "/api/webmcp/preview")
        _, shared = self.request("POST", "/api/webmcp/share", {
            "request_id": f"{name}-share", "confirm": True,
            "confirmation_token": preview["confirmation_token"]})
        return str(shared["session_id"])


def _by_session(geo: dict, session_id: str) -> dict:
    rows = [p for p in geo["people"] if p["session_id"] == session_id]
    assert len(rows) == 1, f"expected exactly one row for {session_id}, got {len(rows)}"
    return rows[0]


class GeoRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pending = build_runtime(":memory:", allowed_origins=frozenset({"pending"}))
        server = serve("127.0.0.1", 0, runtime=pending)
        host, port = server.server_address[:2]
        cls.base = f"http://{host}:{port}"
        server.RequestHandlerClass.runtime = build_runtime(
            ":memory:", allowed_origins=frozenset({cls.base}))
        cls.server = server
        cls.thread = threading.Thread(target=server.serve_forever, daemon=True)
        cls.thread.start()

        # The cast: three people in three different regions who said where
        # they are, one who did not, and three more in one region so that a
        # single bucket clears the minimum of three.
        cls.placed = {}
        for name, location in (
            ("bea", {"city": "Lisbon", "region": "Lisboa", "lat": 38.7166, "lon": -9.1399}),
            ("cai", {"city": "Tallinn", "region": "Harju", "lat": 59.4, "lon": 24.8}),
            ("dov", {"city": "Reykjavik", "region": "Capital Region", "lat": 64.1, "lon": -21.9}),
            ("eli", {"city": "Uppsala", "region": "Testshire", "lat": 59.9, "lon": 17.6}),
            ("fay", {"city": "Lund", "region": "Testshire", "lat": 55.7, "lon": 13.2}),
            ("gus", {"city": "Umeå", "region": "Testshire", "lat": 63.8, "lon": 20.3}),
        ):
            client = Client(cls.base)
            client.guest()
            cls.placed[name] = client.share(name, location)
        cls.placeless = Client(cls.base)
        cls.placeless.guest()
        cls.placeless_session = cls.placeless.share("hal")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def _viewer(self, name: str, location=None):
        viewer = Client(self.base)
        viewer.guest()
        viewer.share(name, location)
        _, geo = viewer.request("GET", "/api/geo")
        return viewer, geo

    def test_without_a_shared_thought_there_is_nobody_to_place(self):
        # No cookie at all, and a guest who has shared nothing: both answer
        # the same product state /api/discover answers, never a fault.
        with self.assertRaises(HTTPError) as ctx:
            urlopen(self.base + "/api/geo", timeout=10)
        self.assertEqual(ctx.exception.code, 409)
        self.assertEqual(json.loads(ctx.exception.read().decode())["error"], "share_required")

        fresh = Client(self.base)
        fresh.guest()
        with self.assertRaises(HTTPError) as ctx:
            fresh.request("GET", "/api/geo")
        self.assertEqual(ctx.exception.code, 409)

    def test_a_browser_share_carries_the_coarse_location_it_was_given(self):
        # The page's prepare route used to drop `coarse_location` and record
        # no consent, so nobody who shared from a browser was ever on the map.
        _, geo = self._viewer("ivy")
        self.assertEqual(geo["contract_version"], "resonance-geo-view/0.1")
        bea = _by_session(geo, self.placed["bea"])
        self.assertEqual(bea["place"]["city"], "Lisbon")
        self.assertEqual(bea["place"]["region"], "Lisboa")

    def test_coordinates_are_rounded_and_carry_no_record_bookkeeping(self):
        _, geo = self._viewer("jan")
        bea = _by_session(geo, self.placed["bea"])
        # 38.7166 / -9.1399 went in; a tenth of a degree comes out.
        self.assertEqual(bea["place"], {"city": "Lisbon", "region": "Lisboa",
                                        "lat": 38.7, "lon": -9.1})
        for person in geo["people"]:
            if person["place"] is not None:
                self.assertEqual(set(person["place"]), {"city", "region", "lat", "lon"})
                self.assertEqual(person["place"]["lat"], round(person["place"]["lat"], 1))
                self.assertEqual(person["place"]["lon"], round(person["place"]["lon"], 1))

    def test_a_person_without_a_place_is_listed_not_dropped(self):
        _, geo = self._viewer("kim")
        hal = _by_session(geo, self.placeless_session)
        self.assertIsNone(hal["place"])
        self.assertIsNone(hal["about_km"])
        self.assertTrue(hal["name"])
        self.assertFalse(hal["example"])

    def test_regions_below_the_minimum_stay_uncounted(self):
        _, geo = self._viewer("lou")
        regions = geo["regions"]
        self.assertEqual(regions["minimum"], 3)
        shown = {b["region"]: b["count"] for b in regions["shown"]}
        # Three people in Testshire clear the bar; Lisboa, Harju and the
        # Capital Region, one person each, do not, and are only counted as
        # "hidden" -- never named.
        self.assertEqual(shown.get("Testshire"), 3)
        for lone in ("Lisboa", "Harju", "Capital Region"):
            self.assertNotIn(lone, shown)
        self.assertGreaterEqual(regions["hidden"], 3)
        for bucket in regions["shown"]:
            self.assertGreaterEqual(bucket["count"], regions["minimum"])

    def test_your_own_place_and_distances_need_your_consent(self):
        _, without = self._viewer("mia")
        self.assertIsNone(without["you"])
        self.assertTrue(all(p["about_km"] is None for p in without["people"]))

        _, with_place = self._viewer("nat", {"city": "Porto", "region": "Norte",
                                              "lat": 41.15, "lon": -8.61})
        self.assertEqual(with_place["you"], {"city": "Porto", "region": "Norte",
                                             "lat": 41.1, "lon": -8.6})
        bea = _by_session(with_place, self.placed["bea"])
        self.assertIsInstance(bea["about_km"], int)
        self.assertLess(bea["about_km"], 400)         # Porto to Lisbon
        hal = _by_session(with_place, self.placeless_session)
        self.assertIsNone(hal["about_km"])             # only with both consents

    def test_the_view_is_the_same_result_the_page_already_reads(self):
        viewer, geo = self._viewer("oli")
        _, discover = viewer.request("GET", "/api/discover")
        visible = [row for row in discover["matches"]
                   if row["display"]["share_state"] == "discoverable"
                   and row["hard_rejection"] is None]
        self.assertEqual([p["session_id"] for p in geo["people"]],
                         [row["session_id"] for row in visible])
        self.assertEqual([p["name"] for p in geo["people"]],
                         [row["person_pseudonym"] for row in visible])
        for person, row in zip(geo["people"], visible):
            expected = row["display"].get("location")
            self.assertEqual(person["place"] is not None, expected is not None)
            self.assertEqual(person["resonance"], row["mode_classification"] != "negative")


NODE = shutil.which("node")

# What the page says for a given view, as the module builds it. Run in Node
# so the words can be checked without a browser; the module renders nothing
# when there is no document.
SENTENCES_SCRIPT = """
import { sentences, geoModel } from %(module)s;
const payload = JSON.parse(process.argv[1]);
const model = geoModel(payload);
console.log(JSON.stringify({
  sentences: sentences(payload),
  points: model.points.map((p) => [p.name, p.x, p.y]),
}));
"""


def _node_sentences(payload: dict) -> dict:
    script = SENTENCES_SCRIPT % {"module": json.dumps(str(UI_DIR / "geo.mjs"))}
    done = subprocess.run([NODE, "--input-type=module", "-e", script, "--", json.dumps(payload)],
                          capture_output=True, text=True, timeout=30, cwd=str(REPO))
    if done.returncode != 0:
        raise AssertionError(done.stderr)
    return json.loads(done.stdout)


def _view(people, you=None, regions=None):
    return {"contract_version": "resonance-geo-view/0.1", "you": you, "people": people,
            "regions": regions or {"minimum": 3, "hidden": 0, "shown": []},
            "rounded_to_degrees": 0.1, "note": ""}


def _person(session_id, name, place=None, **extra):
    row = {"session_id": session_id, "name": name, "resonance": True,
           "example": False, "place": place, "about_km": None}
    row.update(extra)
    return row


@unittest.skipUnless(NODE, "node is not installed; the page module cannot be run here")
class GeoWordsTests(unittest.TestCase):
    def test_nobody_and_nobody_placed_read_differently(self):
        # No people: nothing at all. People who all chose not to say: one
        # sentence that says so. Neither is an empty map.
        self.assertEqual(_node_sentences(_view([]))["sentences"], [])
        placeless = _view([_person("ses-1", "Quiet Mason"), _person("ses-2", "Wry Potter")])
        self.assertEqual(_node_sentences(placeless)["sentences"],
                         ["Nobody who matched has said where they are, so there is no map of them."])

    def test_the_placeless_are_named_and_the_placed_are_placed(self):
        payload = _view([
            _person("ses-a", "Quick Prospector",
                    {"city": "Tallinn", "region": "Harju", "lat": 59.4, "lon": 24.8}, about_km=3320),
            _person("ses-b", "Gabe S.", example=True, resonance=False),
            _person("ses-c", "Velvet Pilgrim",
                    {"city": "Berlin", "region": "Berlin", "lat": 52.5, "lon": 13.4}),
        ], you={"city": "Lisbon", "region": "Lisboa", "lat": 38.7, "lon": -9.1},
           regions={"minimum": 3, "hidden": 2, "shown": [{"region": "Testshire", "count": 3}]})
        lines = _node_sentences(payload)["sentences"]
        self.assertIn("2 of 3 people shared where they are.", lines)
        self.assertIn("You: Lisbon, Lisboa.", lines)
        self.assertIn("Quick Prospector: Tallinn, Harju · about 3,320 km from you", lines)
        self.assertIn("Velvet Pilgrim: Berlin", lines)        # city and region the same
        self.assertIn("Gabe S. chose not to say where they are.", lines)
        self.assertIn("Counted by region: Testshire 3. 2 regions with fewer than 3 people are "
                      "not counted, so nobody can be picked out by where they are.", lines)
        self.assertTrue(any("never affects who matches" in line for line in lines))

    def test_nothing_a_person_reads_is_an_identifier_or_a_raw_float(self):
        payload = _view([
            _person("ses-26280ebbfc183d23", "Faithful Harper",
                    {"city": "Nairobi", "region": "East Africa", "lat": -1.3, "lon": 36.8},
                    about_km=7071.0678),
            _person("ses-kwame-traffic", "Kwame A."),
        ], you={"city": "Kyoto", "region": "Kansai", "lat": 35.0, "lon": 135.8})
        text = "\n".join(_node_sentences(payload)["sentences"])
        self.assertNotRegex(text, r"ses-|person-|result-|r_[0-9a-f]")
        self.assertNotRegex(text, r"\d\.\d{3,}")
        self.assertIn("about 7,071 km from you", text)

    def test_two_people_at_one_rounded_spot_are_both_pointable(self):
        same = {"city": "Berlin", "region": "Berlin", "lat": 52.5, "lon": 13.4}
        payload = _view([_person("ses-a", "One", same), _person("ses-b", "Two", same),
                         _person("ses-c", "Three", same)])
        points = _node_sentences(payload)["points"]
        self.assertEqual([p[0] for p in points], ["One", "Two", "Three"])
        self.assertEqual(len({(p[1], p[2]) for p in points}), 3)

    def test_a_long_list_of_the_placeless_is_counted_not_crowded(self):
        names = ["Ann", "Ben", "Cal", "Dee", "Eve", "Fin", "Gil", "Hal"]
        payload = _view([_person(f"ses-{i}", n) for i, n in enumerate(names)] +
                        [_person("ses-x", "Placed", {"city": "Oslo", "region": "Oslo",
                                                     "lat": 59.9, "lon": 10.8})])
        lines = _node_sentences(payload)["sentences"]
        self.assertIn("Ann, Ben, Cal, Dee, Eve, Fin and 2 others chose not to say where they are.",
                      lines)


class GeoWiringTests(unittest.TestCase):
    def test_the_stylesheet_uses_only_palette_tokens(self):
        # Served under default-src 'self', the panel has no inline styles, and
        # the sheet never names a colour of its own, so light and dark both
        # come from styles.css.
        css = (UI_DIR / "geo.css").read_text(encoding="utf-8")
        self.assertNotRegex(css, r"#[0-9a-fA-F]{3,8}\b")
        self.assertNotRegex(css, r"\b(rgb|rgba|hsl)\(")
        self.assertIn("var(--paper", css)
        self.assertIn("var(--ink", css)
        self.assertIn("var(--accent", css)
        module = (UI_DIR / "geo.mjs").read_text(encoding="utf-8")
        self.assertNotIn(".style.", module)
        self.assertNotIn("<style", module)

    def test_the_page_links_the_sheet_and_the_server_loads_the_module(self):
        html = (UI_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="/geo.css"', html)
        self.assertIn('id="people"', html)
        server = (REPO / "src" / "product" / "server.py").read_text(encoding="utf-8")
        self.assertIn('src="/geo.mjs"', server)
        self.assertIn('"/geo.mjs"', server)
        self.assertIn('"/geo.css"', server)


if __name__ == "__main__":
    unittest.main()
