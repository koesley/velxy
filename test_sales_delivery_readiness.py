import sqlite3
import unittest
import sales_pipeline


class DeliveryReadinessTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        sales_pipeline.setup(self.c)

    def tearDown(self):
        self.c.close()

    def add(self, owner, business, email="", stage="new"):
        return sales_pipeline.save(self.c, owner, {
            "business": business, "email": email, "stage": stage
        })

    def test_default_hold_and_missing_email(self):
        self.add(1, "Example One", "hello@example.com")
        self.add(1, "Example Two")
        r = sales_pipeline.delivery_readiness(self.c, 1)
        self.assertEqual((r["open"], r["held"], r["missing"]), (2, 1, 1))

    def test_suppression_and_manual_verification(self):
        self.add(1, "Example One", "HELLO@EXAMPLE.COM")
        self.add(1, "Example Two", "stop@example.com")
        sales_pipeline.set_suppression(self.c, 1, "hello@example.com",
                                       "verified_clear", "Public contact page checked today")
        sales_pipeline.set_suppression(self.c, 1, "stop@example.com", "do_not_contact")
        r = sales_pipeline.delivery_readiness(self.c, 1)
        self.assertEqual((r["reviewed"], r["suppressed"], r["held"]), (1, 1, 0))
        self.assertEqual(len(r["preview"]), 1)

    def test_owner_isolation_and_closed_leads(self):
        self.add(1, "Owner One", "one@example.com")
        self.add(2, "Owner Two", "two@example.com")
        self.add(1, "Closed Deal", "won@example.com", "won")
        r = sales_pipeline.delivery_readiness(self.c, 1)
        self.assertEqual(r["open"], 1)
        self.assertNotIn("Owner Two", str(r))

    def test_html_escaping(self):
        self.add(1, "<img src=x onerror=alert(1)>", "test@example.com")
        result = sales_pipeline.delivery_readiness_html(self.c, 1)
        self.assertNotIn("<img", result)
        self.assertIn("&lt;img", result)

    def test_preview_bounded_counts_complete(self):
        for i in range(30):
            self.add(1, "Example %02d" % i, "lead%d@example.com" % i)
        r = sales_pipeline.delivery_readiness(self.c, 1, limit=5)
        self.assertEqual(r["held"], 30)
        self.assertEqual(len(r["preview"]), 5)

    def test_limit_validation(self):
        for invalid in (0, 101, -1, "20"):
            with self.assertRaises(ValueError):
                sales_pipeline.delivery_readiness(self.c, 1, limit=invalid)

    def test_dashboard_integration(self):
        self.add(1, "Example One", "hello@example.com")
        page = sales_pipeline.dashboard(self.c, 1, "csrf")
        self.assertIn("Lead contact readiness", page)
        self.assertIn("awaiting verification", page)
        self.assertIn("no messages are sent", page)


if __name__ == "__main__":
    unittest.main()
