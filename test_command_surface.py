"""Static regression checks for the shared command-surface design."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent

class CommandSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = (ROOT / "style.css").read_text(encoding="utf-8")
        cls.portal = (ROOT / "portal.py").read_text(encoding="utf-8")

    def test_production_stylesheet_includes_command_center_design(self):
        # The separate studio CSS route is intentionally disabled on hosted
        # deployments; the public stylesheet must include it instead.
        self.assertIn("(ROOT/'site-studio.css').read_bytes()", self.portal)
        self.assertNotIn('<link rel="stylesheet" href="/site-studio.css">', self.portal)
        studio = (ROOT / "site-studio.css").read_text(encoding="utf-8")
        self.assertIn(".cmd-shell", studio)
        self.assertIn(".studio-panel", studio)

    def test_skip_link_has_matching_main_target(self):
        self.assertIn('class="vx-skip" href="#vx-main"', self.portal)
        self.assertIn('<main id="vx-main">{body}</main>', self.portal)

    def test_mobile_and_reduced_motion_are_supported(self):
        self.assertIn("@media(max-width:760px)", self.css)
        self.assertIn("@media(max-width:480px)", self.css)
        self.assertIn("@media(prefers-reduced-motion:reduce)", self.css)

    def test_navigation_and_focus_are_accessible(self):
        self.assertIn(".velx-more-panel", self.css)
        self.assertIn("max-height:min(65vh,620px)", self.css)
        self.assertIn("a:focus-visible", self.css)
        self.assertIn(".vx-skip:focus", self.css)

if __name__ == "__main__":
    unittest.main()
