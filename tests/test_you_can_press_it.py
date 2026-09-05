"""One first heading, and nothing too small to press (2026-09-05).

Two defects found by measuring the live page rather than looking at it, both
invisible to anyone who reads the markup and both real for someone who does not
read it the way its author does.

*The document had no h1 once a thought was shared.* The first-level heading
lived in the marketing hero, and the hero is hidden the moment there is a
thought -- so the page a person actually spends their time on opened on an h2,
under a section ("While you were away") that is not what the page is about.
Somebody navigating by headings lands nowhere. The fix is not to move the h1
around with the state, which only moves the hole: the page's heading is the
page's name, in the masthead, present in every state and first in the document,
and every section under it is an h2.

*Controls were 12 to 21 pixels tall.* Disclosure rows were the height of their
own text; the name buttons under the map were a line of text with no padding;
and the two maps are drawn in their own coordinate systems and then scaled to
the column, so a marker written as a 6px radius is 12px on a desktop and 7px on
a phone -- the one place it is certainly being pressed with a thumb. Hence
`sizeHitAreas`: the target is computed from the width the map is actually drawn
at, and recomputed when that changes. `vector-effect: non-scaling-stroke` says
the same thing in one line of CSS and was tried first; Chrome draws it and does
not hit-test it, which is worse than not having it.

These are static checks over the markup and the modules. They cannot see a
rendered box -- that measurement is what found the defects, in a browser -- but
they can refuse the shapes that caused them, which is what a regression needs.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "demo" / "ui"
HTML = (UI / "index.html").read_text(encoding="utf-8")
STYLES = (UI / "styles.css").read_text(encoding="utf-8")
GEO_CSS = (UI / "geo.css").read_text(encoding="utf-8")
GEO = (UI / "geo.mjs").read_text(encoding="utf-8")
APP = (UI / "app.mjs").read_text(encoding="utf-8")

MINIMUM = 24


class OneFirstHeadingTests(unittest.TestCase):
    def test_the_page_has_exactly_one_h1(self):
        self.assertEqual(len(re.findall(r"<h1\b", HTML)), 1, HTML.count("<h1"))

    def test_it_is_the_masthead_and_it_comes_first(self):
        # First in the document, so no section can ever precede it -- which is
        # what happened when it lived inside the hero.
        h1 = HTML.index("<h1")
        self.assertIn('class="brand-title"', HTML[h1:h1 + 80])
        self.assertLess(h1, HTML.index("<main"))

    def test_the_hero_is_a_section_heading_now(self):
        self.assertIn('<h2 class="intro-title">', HTML)

    def test_no_module_promotes_a_heading_at_runtime(self):
        # An h1 that appears and disappears with the state is the same hole in
        # a different place, and it cannot be checked by reading the markup.
        for name, source in (("app.mjs", APP), ("geo.mjs", GEO)):
            with self.subTest(name):
                self.assertNotIn('createElement("h1")', source)


class ReachableTargetTests(unittest.TestCase):
    def test_a_disclosure_row_is_at_least_the_minimum(self):
        self.assertRegex(STYLES, r"summary \{[^}]*min-height: %dpx" % MINIMUM)

    def test_the_name_under_the_map_is_at_least_the_minimum(self):
        self.assertRegex(GEO_CSS, r"\.geo-name \{[^}]*min-height: %dpx" % MINIMUM)

    def test_the_wordmark_is_at_least_the_minimum(self):
        self.assertRegex(STYLES, r"\.brand \{[^}]*min-height: %dpx" % MINIMUM)

    def test_both_maps_size_their_targets_from_the_width_they_are_drawn_at(self):
        for name, source in (("geo.mjs", GEO), ("app.mjs", APP)):
            with self.subTest(name):
                self.assertIn(f"const MIN_TARGET = {MINIMUM};", source)
                self.assertIn("getBoundingClientRect().width", source)
                self.assertIn("ResizeObserver", source)

    def test_the_hit_area_is_filled_because_none_is_not_hittable(self):
        # `fill: none` on the disc would leave a target that is there in the
        # markup and absent under the pointer -- the failure this replaced.
        self.assertRegex(GEO_CSS, r"\.geo-hit \{ fill: transparent; \}")
        self.assertRegex(STYLES, r"\.marker-hit \{ fill: transparent; \}")

    def test_no_map_relies_on_a_stroke_chrome_will_not_hit_test(self):
        for name, source in (("geo.css", GEO_CSS), ("styles.css", STYLES)):
            with self.subTest(name):
                self.assertNotIn("pointer-events: stroke", source)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
