"""Regression checks for production persistence preflight (no secrets or network)."""
import unittest
from pathlib import Path
import deployment_readiness_v43 as readiness


class DurableDeploymentTests(unittest.TestCase):
    def inspect(self, **overrides):
        env = {
            "VELXTRIA_REQUIRE_PERSISTENCE": "1",
            "VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT": "0",
        }
        env.update(overrides)
        return {x["check"]: x for x in readiness.inspect(
            Path(__file__).resolve().parent, environ=env)["checks"]}

    def test_missing_database_and_storage_fail_closed(self):
        checks = self.inspect()
        self.assertFalse(checks["durable_database"]["ok"])
        self.assertFalse(checks["private_report_storage"]["ok"])

    def test_database_alone_is_not_enough_for_reports(self):
        checks = self.inspect(VELXTRIA_DATABASE_URL="postgresql://example.invalid/db")
        self.assertTrue(checks["durable_database"]["ok"])
        self.assertFalse(checks["private_report_storage"]["ok"])

    def test_both_persistence_services_pass_preflight(self):
        checks = self.inspect(
            VELXTRIA_DATABASE_URL="postgresql://example.invalid/db",
            VELXTRIA_SUPABASE_URL="https://example.supabase.co",
            VELXTRIA_SUPABASE_SERVICE_KEY="dummy-for-offline-test")
        self.assertTrue(checks["durable_database"]["ok"])
        self.assertTrue(checks["private_report_storage"]["ok"])

    def test_render_rejects_disabled_persistence_even_with_database(self):
        checks = self.inspect(
            VELXTRIA_DEPLOYMENT_MODE="render-preview",
            VELXTRIA_REQUIRE_PERSISTENCE="0",
            VELXTRIA_DATABASE_URL="postgresql://example.invalid/db",
            VELXTRIA_SUPABASE_URL="https://example.supabase.co",
            VELXTRIA_SUPABASE_SERVICE_KEY="offline-test-key")
        self.assertFalse(checks["render_persistence_enforced"]["ok"])

    def test_render_requires_both_storage_services(self):
        checks = self.inspect(VELXTRIA_DEPLOYMENT_MODE="render-preview")
        self.assertTrue(checks["render_persistence_enforced"]["ok"])
        self.assertFalse(checks["durable_database"]["ok"])
        self.assertFalse(checks["private_report_storage"]["ok"])

    def test_local_development_does_not_require_remote_storage(self):
        env = {"VELXTRIA_REQUIRE_PERSISTENCE": "0",
               "VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT": "0"}
        checks = {x["check"]: x for x in readiness.inspect(
            Path(__file__).resolve().parent, environ=env)["checks"]}
        self.assertNotIn("durable_database", checks)
        self.assertNotIn("private_report_storage", checks)


if __name__ == "__main__":
    unittest.main()
