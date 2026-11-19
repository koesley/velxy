"""Tests for Genesis Forge's preview-only application blueprint compiler."""
import unittest
from genesis_forge_v1 import compile_blueprint, validate_manifest


class GenesisForgeTests(unittest.TestCase):
    def test_cleaning_template(self):
        m = compile_blueprint("workspace_123", "Cleaning Operations", "cleaning")
        self.assertEqual([b["type"] for b in m["components"]],
                         ["crm", "schedule", "tasks", "quotes"])
        self.assertEqual(m["status"], "preview_only")
        self.assertFalse(m["external_actions_enabled"])
        self.assertFalse(m["custom_code_enabled"])
        self.assertTrue(validate_manifest(m, "workspace_123"))

    def test_deterministic(self):
        self.assertEqual(compile_blueprint("abc", "My App"),
                         compile_blueprint("abc", "My App"))

    def test_tenant_boundary(self):
        m = compile_blueprint("tenant_a", "App")
        with self.assertRaises(ValueError):
            validate_manifest(m, "tenant_b")

    def test_tamper_rejected(self):
        m = compile_blueprint("tenant_a", "App")
        m["components"][0]["permissions"].append("admin:write")
        with self.assertRaises(ValueError):
            validate_manifest(m, "tenant_a")

    def test_rejects_unsafe_components(self):
        for components in (["shell"], ["crm", "crm"], [], ["crm", "python"]):
            with self.subTest(components=components):
                with self.assertRaises(ValueError):
                    compile_blueprint("tenant_a", "App", components=components)

    def test_rejects_invalid_workspace(self):
        with self.assertRaises(ValueError):
            compile_blueprint("../other", "App")


if __name__ == "__main__":
    unittest.main()
