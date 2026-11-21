"""Email conversion and safe-summary regression tests.

Run: python -m unittest -v test_demo_email_conversion
"""
import unittest
import demo_leads


class DemoEmailConversionTests(unittest.TestCase):
    def setUp(self):
        self.shared = {
            "accepted": 3, "rejected": 1,
            "stats": ["Revenue: $300"],
            "monthly_rows": [["Month", "Revenue"], ["2026-11", "300"]],
            "product_rows": [["Product", "Revenue"], ["Service", "300"]],
        }

    def render(self, report=None):
        return demo_leads.format_email_body(
            report or self.shared,
            "https://velxtria.example/demo/abc",
            "https://velxtria.example")

    def test_email_points_to_existing_inline_signup(self):
        body = self.render()
        self.assertIn("https://velxtria.example/demo/abc", body)
        self.assertIn("create your free account directly from that page", body)
        self.assertIn("saved as part of signup", body)
        self.assertIn("/login", body)
        self.assertNotIn("then claim this demo from your dashboard", body)

    def test_long_aggregates_are_bounded_and_disclosed(self):
        report = dict(self.shared)
        report["monthly_rows"] = [[str(i), "1"] for i in range(100)]
        report["product_rows"] = [[str(i), "1"] for i in range(100)]
        body = self.render(report)
        self.assertIn("75 additional summary rows", body)
        self.assertNotIn("99 | 1", body)
        self.assertIn("24 | 1", body)
        self.assertIn("view the full report online", body)

    def test_untrusted_cells_cannot_inject_new_email_lines(self):
        report = dict(self.shared)
        report["product_rows"] = [["Name", "Value"], ["bad\r\nForged: yes", "x" * 500]]
        body = self.render(report)
        self.assertIn("bad  Forged: yes", body)
        self.assertNotIn("\r", body)
        self.assertNotIn("x" * 300, body)

    def test_no_raw_customer_rows_added(self):
        body = self.render()
        self.assertNotIn("Customer", body)
        self.assertIn("Revenue: $300", body)


if __name__ == "__main__":
    unittest.main()
