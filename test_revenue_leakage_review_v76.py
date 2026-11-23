import unittest
from revenue_leakage_review_v76 import review_export


class ExportReviewTests(unittest.TestCase):
    def test_authorized_export(self):
        result = review_export({"subscriptions": [
            {"subscription_id": "sub_1", "monthly_amount": "49", "status": "past_due", "failed_payment_count": 1}
        ]}, "2026-11-22")
        self.assertEqual(result["monthly_revenue_at_risk"], "49.00")
        self.assertTrue(result["opportunities"][0]["requires_approval"])

    def test_rejects_extra_personal_data(self):
        with self.assertRaises(ValueError):
            review_export({"subscriptions": [{"subscription_id": "a", "monthly_amount": 10, "status": "active", "email": "private@example.com"}]}, "2026-11-22")

    def test_rejects_malformed_export(self):
        with self.assertRaises(ValueError):
            review_export([], "2026-11-22")


if __name__ == "__main__":
    unittest.main()
