"""Static regression checks for the shared command-surface design."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent

class CommandSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = (ROOT / "style.css").read_text(encoding="utf-8")
        cls.portal = (ROOT / "portal.py").read_text(encoding="utf-8")

    def test_security_policy_allows_only_same_origin_scripts(self):
        self.assertIn("script-src 'self'; form-action 'self'", self.portal)
        self.assertNotIn("script-src 'none'; form-action 'self'", self.portal)
        self.assertNotIn("script-src 'unsafe-inline'", self.portal)
        render = (ROOT / "render.yaml").read_text(encoding="utf-8")
        # The build must run the command-surface tests. Check each name
        # separately: the list grows as new command-surface modules are
        # added, and a single contiguous substring would break every time
        # one is inserted between two others.
        for name in ("test_invoice_integrity", "test_command_surface",
                     "test_http_command_surface", "test_site_stats"):
            self.assertIn(name, render)

    def test_production_css_cascade_applies_design_last(self):
        route = self.portal.split("if p=='/style.css':return self.respond(200,",1)[1].split("\n",1)[0]
        self.assertLess(route.index("LANDING_CSS+WORKSPACE_CSS"), route.index("(ROOT/'site-studio.css').read_bytes()"))
        self.assertLess(route.index("(ROOT/'site-studio.css').read_bytes()"), route.index("(ROOT/'style.css').read_bytes()"))
        self.assertIn("+b'\\n'+", route)

    def test_active_page_navigation_and_style(self):
        script = (ROOT / "command-palette.js").read_text(encoding="utf-8")
        self.assertIn("window.location.pathname", script)
        self.assertIn("link.setAttribute('aria-current', 'page')", script)
        self.assertIn('.velx-nav a[aria-current="page"]', self.css)

    def test_personal_quick_launch_is_scoped_and_accessible(self):
        script = (ROOT / "command-palette.js").read_text(encoding="utf-8")
        self.assertIn("const STORE = 'vx-command-launch-v2:' + scope", script)
        self.assertIn("document.body.dataset.vxWorkspaceScope", script)
        self.assertIn('data-vx-workspace-scope="{escape(str(user[\'id\'])) if user else \'guest\'}"', self.portal)
        self.assertIn("allowed.has(url)", script)
        self.assertIn("localStorage.getItem(STORE)", script)
        self.assertIn("localStorage.setItem(STORE", script)
        self.assertIn("state.pinned.includes(url)", script)
        self.assertIn("state.recent.includes(url)", script)
        self.assertIn("pin.setAttribute('aria-pressed'", script)
        self.assertIn("pin.setAttribute('aria-label'", script)
        self.assertIn("pin.addEventListener('click'", script)
        self.assertIn(".vx-command-pin", self.css)
        self.assertNotIn("innerHTML", script)

    def test_command_palette_indexes_actual_navigation(self):
        script = (ROOT / "command-palette.js").read_text(encoding="utf-8")
        self.assertIn("document.querySelectorAll('header nav a[href]')", script)
        self.assertIn("new Map()", script)
        self.assertIn("name === q ? 4", script)
        self.assertIn("name.startsWith(q) ? 3", script)
        self.assertIn(".sort((a,b) => b.score - a.score", script)
        self.assertIn("url.startsWith('/')", script)
        self.assertIn("!url.startsWith('//')", script)
        self.assertNotIn("['Business OS','/business-os-v59'", script)
        self.assertIn("event.key === 'ArrowDown'", script)
        self.assertIn("event.key === 'ArrowUp'", script)
        self.assertIn("input.focus()", script)

    def test_command_palette_is_served_and_linked(self):
        self.assertIn('<script defer src="/command-palette.js"></script>', self.portal)
        self.assertIn("if p=='/command-palette.js':", self.portal)
        self.assertIn("(ROOT/'command-palette.js').read_bytes()", self.portal)
        self.assertIn('id="vx-command-dialog"', self.portal)
        self.assertIn('id="vx-command-search"', self.portal)
        self.assertIn('id="vx-command-open"', self.portal)
        script = (ROOT / "command-palette.js").read_text(encoding="utf-8")
        self.assertIn("dialog.showModal()", script)
        self.assertIn("event.key.toLowerCase() === 'k'", script)
        self.assertIn("results.replaceChildren()", script)
        self.assertNotIn("innerHTML", script)
        self.assertIn(".vx-command-dialog", self.css)

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
