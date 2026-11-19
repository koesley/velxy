"""Regression checks for Genesis Forge create form and preview routes."""
import pathlib
import unittest


class GenesisForgeCreateRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = pathlib.Path(__file__).with_name("portal.py").read_text(encoding="utf-8")

    def test_create_uses_existing_csrf_gate(self):
        source = self.source
        csrf = source.index("if not hmac.compare_digest(fields.get('csrf',''),csrf)")
        create = source.index("if p=='/genesis-forge/create':")
        self.assertLess(csrf, create)
        self.assertIn("genesis_forge_service_v1.create_preview(", source[create:create+500])

    def test_get_preview_requires_authorized_service(self):
        section = self.source.split("if p=='/genesis-forge':", 1)[1].split("if p=='/founder-stats':", 1)[0]
        self.assertIn("auth=self.require()", section)
        self.assertIn("genesis_forge_service_v1.get_preview(", section)
        self.assertIn("html.escape(block['label'],quote=True)", section)

    def test_create_form_contains_csrf_and_workspace(self):
        section = self.source.split("if p=='/genesis-forge':", 1)[1].split("if p=='/founder-stats':", 1)[0]
        self.assertIn('name="csrf"', section)
        self.assertIn('name="workspace"', section)
        self.assertIn('action="/genesis-forge/create"', section)


if __name__ == "__main__":
    unittest.main()
