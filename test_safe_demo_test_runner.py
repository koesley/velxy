"""Regression coverage for production-safe HTTP test execution."""
import os
import tempfile
import unittest
from unittest.mock import patch
import safe_demo_test_runner as runner


class SafeDemoRunnerTests(unittest.TestCase):
    def test_removes_production_credentials(self):
        source = {key: "secret" for key in runner.UNSAFE_KEYS}
        source.update({"VELXTRIA_REQUIRE_PERSISTENCE": "1",
                       "VELXTRIA_DEPLOYMENT_MODE": "render-preview",
                       "VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT": "1",
                       "UNRELATED": "keep"})
        env = runner.isolated_environment(source, "/tmp/test-only")
        for key in runner.UNSAFE_KEYS:
            self.assertNotIn(key, env)
        self.assertEqual(env["VELXTRIA_REQUIRE_PERSISTENCE"], "0")
        self.assertEqual(env["VELXTRIA_DEPLOYMENT_MODE"], "local")
        self.assertEqual(env["VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT"], "0")
        self.assertEqual(env["UNRELATED"], "keep")
        self.assertEqual(source["VELXTRIA_REQUIRE_PERSISTENCE"], "1")

    def test_invokes_unittest_in_isolated_subprocess(self):
        with patch.object(runner.subprocess, "call", return_value=0) as call:
            self.assertEqual(runner.main(), 0)
        args, kwargs = call.call_args
        self.assertEqual(args[0][:3], [runner.sys.executable, "-m", "unittest"])
        self.assertIn("test_demo_signup", args[0])
        self.assertNotIn("VELXTRIA_DATABASE_URL", kwargs["env"])
        self.assertEqual(kwargs["env"]["VELXTRIA_REQUIRE_PERSISTENCE"], "0")
        self.assertFalse(os.path.exists(kwargs["env"]["VELXTRIA_DATA_DIR"]))

    def test_propagates_failure(self):
        with patch.object(runner.subprocess, "call", return_value=7):
            self.assertEqual(runner.main(), 7)


if __name__ == "__main__":
    unittest.main()
