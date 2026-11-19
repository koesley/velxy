"""Portal wiring regression tests for Genesis Forge."""
import pathlib
import unittest


class GenesisForgePortalWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.portal = pathlib.Path(__file__).with_name("portal.py").read_text(encoding="utf-8")

    def test_import_and_route(self):
        self.assertIn("import genesis_forge_service_v1", self.portal)
        self.assertIn("if p=='/genesis-forge':", self.portal)

    def test_requires_authenticated_identity(self):
        route = self.portal.split("if p=='/genesis-forge':", 1)[1].split("if p=='/founder-stats':", 1)[0]
        self.assertIn("auth=self.require()", route)
        self.assertIn("genesis_forge_service_v1.get_previews(c,user['id'],wid)", route)

    def test_escaped_display_and_no_store(self):
        route = self.portal.split("if p=='/genesis-forge':", 1)[1].split("if p=='/founder-stats':", 1)[0]
        self.assertIn("html.escape(item['name'],quote=True)", route)
        self.assertIn("('Cache-Control','no-store')", route)
        self.assertIn("Create design preview", route)
        self.assertNotIn("update_preview(", route)


if __name__ == "__main__":
    unittest.main()
