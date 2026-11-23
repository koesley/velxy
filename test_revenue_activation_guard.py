"""Prevent V60/V61 guard drift from silently skipping customer-path regressions."""
from pathlib import Path
import re
import unittest

WORKFLOW = Path(__file__).resolve().parent / ".github/workflows/revenue-activation-guard.yml"
MODULES = (
    "test_revenue_dominion_v60", "test_first_value_v61",
    "test_founder_economics", "test_founder_activation", "test_founder_paid_conversion",
    "test_site_stats", "test_signup_path", "test_instant_demo",
    "test_demo_claim", "test_demo_workspace", "test_welcome_sequence",
    "test_ledger", "test_revenue_engine", "test_btcpay_mainnet",
    "test_report_pro_offer", "test_paywall_analytics",
    "test_revenue_activation_guard",
)
SOURCES = (
    "revenue_dominion_v60.py", "first_value_v61.py",
    "founder_economics.py", "founder_activation.py", "founder_paid_conversion.py",
    "portal.py", "ledger.py", "site_stats.py",
    "btcpay_mainnet.py", "subscriptions.py",
)


class RevenueActivationGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.push = cls.workflow.split("\n  push:\n", 1)[1].split("\n  pull_request:\n", 1)[0]
        cls.pr = cls.workflow.split("\n  pull_request:\n", 1)[1].split("\n  schedule:\n", 1)[0]

    def test_every_executed_test_triggers_both_push_and_pr(self):
        for module in MODULES:
            path = module + ".py"
            with self.subTest(path=path):
                self.assertIn("'" + path + "'", self.push)
                self.assertIn("'" + path + "'", self.pr)
                self.assertRegex(self.workflow, r"(?<![\w])" + re.escape(module) + r"(?![\w])")

    def test_customer_source_changes_trigger_both_events(self):
        for path in SOURCES:
            with self.subTest(path=path):
                self.assertIn("'" + path + "'", self.push)
                self.assertIn("'" + path + "'", self.pr)

    def test_all_guarded_modules_are_executed(self):
        command = self.workflow.split("python -m unittest -v", 1)[1]
        for module in MODULES:
            with self.subTest(module=module):
                self.assertRegex(command, r"(?<![\w])" + re.escape(module) + r"(?![\w])")
        self.assertIn("python-version: ['3.11', '3.12', '3.13']", self.workflow)

    def test_billing_verification_is_guarded_as_part_of_activation(self):
        # Billing evidence must be exercised with activation in every scheduled run.
        command = self.workflow.split("python -m unittest -v", 1)[1]
        self.assertIn("test_btcpay_mainnet", command)
        for path in ("btcpay_mainnet.py", "subscriptions.py", "test_btcpay_mainnet.py"):
            with self.subTest(path=path):
                self.assertIn("'" + path + "'", self.push)
                self.assertIn("'" + path + "'", self.pr)

    def test_paid_conversion_customer_paths_are_guarded(self):
        # Exercise first-report upgrade, exhausted-quota paywall and billing
        # in the same job; changes to each test must trigger both events.
        command = self.workflow.split("python -m unittest -v", 1)[1]
        for module in ("test_report_pro_offer", "test_paywall_analytics", "test_btcpay_mainnet"):
            with self.subTest(module=module):
                self.assertRegex(command, r"(?<![\\w])" + re.escape(module) + r"(?![\\w])")
                path = "'" + module + ".py'"
                self.assertIn(path, self.push)
                self.assertIn(path, self.pr)

    def test_guard_cannot_silently_enable_real_checkout(self):
        command = self.workflow.split("Run V60/V61 analytics and real customer-path regressions", 1)[1]
        self.assertIn("VELXTRIA_DEPLOYMENT_MODE: local", command)
        self.assertIn("VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT: '0'", command)
        self.assertIn("PYTHONDONTWRITEBYTECODE: '1'", command)
        self.assertIn("timeout-minutes: 8", self.workflow)

    def test_read_only_offline_guard_and_hourly_schedule(self):
        self.assertIn("contents: read", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)
        self.assertIn("VELXTRIA_DEPLOYMENT_MODE: local", self.workflow)
        self.assertIn("VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT: '0'", self.workflow)
        self.assertIn("cron: '19 * * * *'", self.workflow)
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertIn("'.github/workflows/revenue-activation-guard.yml'", self.push)
        self.assertIn("'.github/workflows/revenue-activation-guard.yml'", self.pr)


if __name__ == "__main__":
    unittest.main()
