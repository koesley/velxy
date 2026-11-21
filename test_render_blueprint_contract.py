"""Fail-closed regression checks for the production Render Blueprint contract.

No network, credentials, or YAML dependency required. Checks only the single
service's currently committed configuration and never prints secret values.
"""
from pathlib import Path
import re
import unittest

BLUEPRINT = Path(__file__).with_name("render.yaml")
REQUIRED_TESTS = (
    "test_deployment_database_url",
    "test_verify_database",
    "test_verify_storage",
    "test_verify_readiness",
    "test_ascension_v28",
)

class RenderBlueprintContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = BLUEPRINT.read_text(encoding="utf-8")
        cls.build = re.search(r'^    buildCommand: "([^"\n]+)"$', cls.source, re.M)
        cls.start = re.search(r'^    startCommand: "([^"\n]+)"$', cls.source, re.M)

    def test_build_command_present_and_all_checks_required(self):
        self.assertIsNotNone(self.build)
        build = self.build.group(1)
        self.assertNotIn("|| true", build)
        self.assertNotIn("; exit 0", build)
        for test in REQUIRED_TESTS:
            with self.subTest(test=test):
                self.assertRegex(build, r"\b" + re.escape(test) + r"\b")
        self.assertIn("python deployment_readiness_v43.py", build)
        self.assertIn("python smoke_http.py", build)
        self.assertIn("python -m compileall -q .", build)

    def test_ascension_suite_runs_in_local_mode(self):
        self.assertIsNotNone(self.build)
        self.assertIn(
            "VELXTRIA_LOCAL_STUDIO=1 VELXTRIA_DEPLOYMENT_MODE=local "
            "python -m unittest -v test_ascension_v28",
            self.build.group(1),
        )

    def test_persistence_and_health_contract(self):
        self.assertIn("healthCheckPath: /health/ready", self.source)
        self.assertIsNotNone(self.start)
        self.assertEqual(self.start.group(1), "python -u portal.py")
        self.assertRegex(
            self.source,
            r"(?m)^      - key: VELXTRIA_REQUIRE_PERSISTENCE\n        value: '1'$",
        )
        self.assertRegex(
            self.source,
            r"(?m)^      - key: VELXTRIA_DATABASE_URL\n        sync: false$",
        )

    def test_sensitive_values_remain_dashboard_controlled(self):
        for key in (
            "VELXTRIA_SUPABASE_SERVICE_KEY",
            "VELXTRIA_PREVIEW_PASSWORD",
            "VELXTRIA_BTCPAY_MAINNET_API_KEY",
            "VELXTRIA_BTCPAY_MAINNET_WEBHOOK_SECRET",
            "VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT",
        ):
            with self.subTest(key=key):
                self.assertRegex(
                    self.source,
                    r"(?m)^      - key: " + re.escape(key) + r"\n        sync: false$",
                )

if __name__ == "__main__":
    unittest.main()
