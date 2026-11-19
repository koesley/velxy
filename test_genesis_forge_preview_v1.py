"""Safety and output tests for the Genesis Forge read-only preview."""
import unittest
from genesis_forge_v1 import compile_blueprint
from genesis_forge_preview_v1 import render_preview


class GenesisForgePreviewTests(unittest.TestCase):
    def test_render_components(self):
        manifest = compile_blueprint("tenant_a", "Cleaning Operations", "cleaning")
        page = render_preview(manifest, "tenant_a")
        self.assertIn("Customer CRM", page)
        self.assertIn("Scheduling", page)
        self.assertIn("Job Tracking", page)
        self.assertIn("Quotes", page)
        self.assertIn('name="viewport"', page)
        self.assertIn("not a deployed application", page)

    def test_escaped_name(self):
        manifest = compile_blueprint("tenant_a", '<img src=x onerror=alert(1)>')
        page = render_preview(manifest, "tenant_a")
        self.assertNotIn('<img src=x', page)
        self.assertIn('&lt;img', page)

    def test_workspace_boundary(self):
        manifest = compile_blueprint("tenant_a", "Operations")
        with self.assertRaises(ValueError):
            render_preview(manifest, "tenant_b")

    def test_reject_modified_manifest(self):
        manifest = compile_blueprint("tenant_a", "Operations")
        manifest["components"][0]["label"] = "<script>bad()</script>"
        with self.assertRaises(ValueError):
            render_preview(manifest, "tenant_a")

    def test_csp_and_no_external_assets(self):
        page = render_preview(compile_blueprint("tenant_a", "Operations"), "tenant_a")
        self.assertIn("Content-Security-Policy", page)
        self.assertIn("default-src &#39;none&#39;", page)
        self.assertNotIn("<script", page)
        self.assertNotIn("<iframe", page)
        self.assertNotIn("<form", page)


if __name__ == "__main__":
    unittest.main()
