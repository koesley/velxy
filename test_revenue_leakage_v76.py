import unittest
from revenue_leakage_v76 import SubscriptionSignal, detect_leakage


class RevenueLeakageTests(unittest.TestCase):
    def test_flags_and_totals(self):
        result = detect_leakage([
            SubscriptionSignal("a", "49", "active"),
            SubscriptionSignal("b", "99", "past_due", 2),
            SubscriptionSignal("c", "20", "active", renewal_date="2026-11-25"),
            SubscriptionSignal("d", "100", "canceled"),
        ], "2026-11-22")
        self.assertEqual(result["active_mrr"], "69.00")
        self.assertEqual(result["monthly_revenue_at_risk"], "119.00")
        self.assertEqual([x["subscription_id"] for x in result["opportunities"]], ["b", "c"])

    def test_no_double_count(self):
        result = detect_leakage([SubscriptionSignal("a", 10, "past_due", 2, cancellation_requested=True)], "2026-11-22")
        self.assertEqual(result["monthly_revenue_at_risk"], "10.00")

    def test_rejects_invalid(self):
        for value in ("NaN", "-1", "Infinity"):
            with self.assertRaises(ValueError):
                detect_leakage([SubscriptionSignal("a", value, "active")], "2026-11-22")
        with self.assertRaises(ValueError):
            detect_leakage([SubscriptionSignal("a", 1, "active"), SubscriptionSignal("a", 2, "active")], "2026-11-22")

    def test_future_and_past_renewals(self):
        result = detect_leakage([
            SubscriptionSignal("a", 10, "active", renewal_date="2026-12-01"),
            SubscriptionSignal("b", 10, "active", renewal_date="2026-11-01"),
        ], "2026-11-22")
        self.assertEqual(result["opportunities"], [])


if __name__ == "__main__":
    unittest.main()
