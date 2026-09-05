"""One type scale, one set of radii (2026-09-05).

Measured on a populated page: nineteen distinct font sizes and six corner
radii, including 12.88px and 17.55px, which nobody chose -- they fell out of
`em` on inherited sizes. That is what "laid out like a hallucination" looks
like from the inside: every component invented its own values on the day it
was written, and nothing said no.

Parshkov was right, and taste is not a defence. So the values are tokens, and
this refuses a raw one. A new size is a decision about the whole page, taken
once, in the block at the top of styles.css -- not a number typed into
whichever rule is being edited.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "demo" / "ui"
SHEETS = sorted(UI.glob("*.css"))

# The scale itself, declared once, in a file of its own. It began inside
# styles.css, which only the product page links -- so when the documentation
# pages were converted to read `var(--text-body)`, every one of those
# declarations was invalid and every size on those pages collapsed to the
# inherited 16px: heading, lede, body and footer all the same. A missing custom
# property is not an error; the rule is dropped and the page still renders,
# which is why nobody saw it until the sizes were measured.
TOKENS = Path(UI / "tokens.css").read_text(encoding="utf-8")
DECLARED = set(re.findall(r"--(text-[a-z0-9]+|radius(?:-[a-z]+)?): ", TOKENS))

# Every page that links a stylesheet must link the scale before it.
PAGES = sorted(UI.glob("*.html"))


class OneScaleTests(unittest.TestCase):
    def test_the_scale_is_declared(self):
        for token in ("text-xs", "text-body", "text-2xl",
                      "radius-xs", "radius-sm", "radius", "radius-pill"):
            self.assertIn(token, DECLARED, token)

    def test_no_stylesheet_invents_a_size(self):
        for sheet in SHEETS:
            with self.subTest(sheet.name):
                raw = re.findall(r"font-size: *([0-9.]+)px", sheet.read_text(encoding="utf-8"))
                self.assertEqual(raw, [],
                                 f"{sheet.name} sets a font size in pixels; "
                                 "use a --text-* token, or add a step to the scale")

    def test_no_stylesheet_invents_a_corner(self):
        for sheet in SHEETS:
            with self.subTest(sheet.name):
                raw = re.findall(r"border-radius: *([0-9.]+)px", sheet.read_text(encoding="utf-8"))
                self.assertEqual(raw, [],
                                 f"{sheet.name} sets a corner radius in pixels; "
                                 "use a --radius* token")

    def test_nothing_is_smaller_than_eleven_pixels(self):
        """Below this it stops being small type and becomes type some people
        cannot read. The page had 9.5px on it."""
        match = re.search(r"--text-xs: *([0-9.]+)px", TOKENS)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(float(match.group(1)), 11.0)

    def test_every_token_used_anywhere_is_declared(self):
        """A `var(--text-md)` that nothing declares does not fail: it is
        dropped, and the element quietly takes whatever it inherits."""
        for sheet in SHEETS:
            if sheet.name == "tokens.css":
                continue
            with self.subTest(sheet.name):
                used = set(re.findall(r"var\(--(text-[a-z0-9]+|radius(?:-[a-z]+)?)\)",
                                      sheet.read_text(encoding="utf-8")))
                missing = sorted(used - DECLARED)
                self.assertEqual(missing, [],
                                 f"{sheet.name} reads {missing}, which tokens.css "
                                 "does not declare")

    def test_every_page_links_the_scale_first(self):
        for page in PAGES:
            text = page.read_text(encoding="utf-8")
            if 'rel="stylesheet"' not in text:
                continue
            with self.subTest(page.name):
                self.assertIn('href="/tokens.css"', text,
                              f"{page.name} links a stylesheet but not the scale")
                # Before the sheets that read it: a custom property must be
                # declared by the time the rule using it is resolved.
                self.assertLess(text.index('href="/tokens.css"'),
                                min(text.index(f'href="/{other.name}"')
                                    for other in SHEETS
                                    if other.name != "tokens.css"
                                    and f'href="/{other.name}"' in text))

    def test_the_signin_page_links_it_too(self):
        """It is built in Python, not from a file in this directory, so the
        glob above cannot see it."""
        mount = (Path(__file__).resolve().parents[1] / "src" / "product"
                 / "auth_mount.py").read_text(encoding="utf-8")
        self.assertIn("/tokens.css", mount)
        self.assertLess(mount.index("/tokens.css"), mount.index("/legal.css"))

    def test_the_footer_is_identity_then_navigation(self):
        """It was a loose paragraph with three underlined words beneath it:
        neither identity nor navigation, and nothing saying the three belonged
        together."""
        page = (UI / "index.html").read_text(encoding="utf-8")
        footer = page[page.index("<footer"):page.index("</footer>")]
        self.assertIn("foot-name", footer)
        self.assertIn('<nav class="foot-nav" aria-label="Footer">', footer)
        self.assertIn("<ul>", footer)
        self.assertEqual(footer.count("<li>"), 3)


if __name__ == "__main__":
    unittest.main()
