"""Regression checks for Genesis Forge visual component editing."""
import pathlib
import unittest


class GenesisForgeEditRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = pathlib.Path(__file__).with_name("portal.py").read_text(encoding="utf-8")

    def test_edit_requires_csrf_and_workspace(self):
        source = self.source
        csrf = source.index("if not hmac.compare_digest(fields.get('csrf',''),csrf)")
        update = source.index("if p=='/genesis-forge/update':")
        self.assertLess(csrf, update)
        section = source.split("if p=='/genesis-forge':", 1)[1].split("if p=='/founder-stats':", 1)[0]
        self.assertIn('action="/genesis-forge/update"', section)
        self.assertIn('name="revision"', section)
        self.assertIn('name="workspace"', section)

    def test_update_uses_authorized_service(self):
        source = self.source
        section = source.split("if p=='/genesis-forge/update':", 1)[1].split("if p=='/ascension-workflow-create':", 1)[0]
        self.assertIn("genesis_forge_service_v1.update_preview(", section)
        self.assertIn("int(fields.get('revision','0'))", section)

    def test_multiple_components_preserved(self):
        self.assertIn("if k=='component' else v[0]", self.source)
        self.assertIn("max_num_fields=100", self.source)

    def test_escaped_display(self):
        section = self.source.split("if p=='/genesis-forge':", 1)[1].split("if p=='/founder-stats':", 1)[0]
        self.assertIn("html.escape(record['manifest']['name'],quote=True)", section)
        self.assertIn("html.escape(block['label'],quote=True)", section)


if __name__ == "__main__":
    unittest.main()
