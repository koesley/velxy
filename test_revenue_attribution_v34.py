import sqlite3
import unittest
from unittest.mock import patch
from revenue_attribution_v34 import analyze, render, _money


class AttributionTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE bos59_leads (id TEXT,workspace_id TEXT,source TEXT,status TEXT)")
        self.c.execute("CREATE TABLE vx_outcomes33 (workspace_id TEXT,lead_id TEXT,kind TEXT,amount_cents INTEGER)")
        self.c.execute("CREATE TABLE vx_revenue_tasks29 (workspace_id TEXT,lead_id TEXT,status TEXT)")
        self.c.executemany("INSERT INTO bos59_leads VALUES (?,?,?,?)", [
            ("a", "one", "Referral", "won"), ("b", "one", "Referral", "new"),
            ("c", "one", "Web <script>", "contacted"), ("d", "two", "Referral", "won")])
        self.c.executemany("INSERT INTO vx_outcomes33 VALUES (?,?,?,?)", [
            ("one", "a", "payment_reported", 12500),
            ("one", "a", "appointment_booked", 0),
            ("two", "d", "payment_reported", 999999)])
        self.c.executemany("INSERT INTO vx_revenue_tasks29 VALUES (?,?,?)", [
            ("one", "a", "done"), ("one", "b", "todo"), ("two", "d", "done")])

    def tearDown(self):
        self.c.close()

    @patch("revenue_attribution_v34.execution.setup")
    @patch("revenue_attribution_v34.outcomes.setup")
    @patch("revenue_attribution_v34.bos.init")
    @patch("revenue_attribution_v34.bos.core.access")
    def test_scoped_aggregation(self, access, init, setup_outcomes, setup_tasks):
        rows = analyze(self.c, 1, "one")
        referral = next(r for r in rows if r["source"] == "Referral")
        self.assertEqual(referral["leads"], 2)
        self.assertEqual(referral["won_share_pct"], 50.0)
        self.assertEqual(referral["closed_win_pct"], 100.0)
        self.assertEqual(referral["reported_cents"], 12500)
        self.assertEqual(referral["payment_leads"], 1)
        self.assertEqual(referral["outcomes"], 2)
        self.assertEqual(referral["completed_tasks"], 1)
        self.assertEqual(referral["task_completion_pct"], 50.0)
        self.assertNotIn("<script>", render(self.c, 1, "one"))
        access.assert_called_with(self.c, 1, "one")

    @patch("revenue_attribution_v34.execution.setup")
    @patch("revenue_attribution_v34.outcomes.setup")
    @patch("revenue_attribution_v34.bos.init")
    @patch("revenue_attribution_v34.bos.core.access")
    def test_closed_denominator_and_distinct_payment_leads(self, *mocks):
        self.c.execute("INSERT INTO bos59_leads VALUES (?,?,?,?)", ("e", "one", "Referral", "lost"))
        self.c.executemany("INSERT INTO vx_outcomes33 VALUES (?,?,?,?)", [
            ("one", "a", "payment_reported", 200),
            ("one", "a", "payment_reported", -500),
            ("one", "a", "payment_reported", None),
            ("one", "missing", "payment_reported", 900000)])
        row = next(r for r in analyze(self.c, 1, "one") if r["source"] == "Referral")
        self.assertEqual(row["closed_leads"], 2)
        self.assertEqual(row["closed_win_pct"], 50.0)
        self.assertEqual(row["won_share_pct"], 33.3)
        self.assertEqual(row["payment_leads"], 1)
        self.assertEqual(row["reported_payments"], 2)
        self.assertEqual(row["reported_cents"], 12700)
        self.assertEqual(row["invalid_payment_records"], 2)
        self.assertIn("Excluded invalid or negative payment claims: 2", render(self.c, 1, "one"))

    @patch("revenue_attribution_v34.execution.setup")
    @patch("revenue_attribution_v34.outcomes.setup")
    @patch("revenue_attribution_v34.bos.init")
    @patch("revenue_attribution_v34.bos.core.access")
    def test_empty_denominators_and_escaping(self, *mocks):
        self.c.execute("INSERT INTO bos59_leads VALUES (?,?,?,?)",
                       ("x", "one", 'Source "><img src=x>', "new"))
        rows = analyze(self.c, 1, "one")
        row = next(r for r in rows if r["source"].startswith("Source"))
        self.assertIsNone(row["closed_win_pct"])
        self.assertIsNone(row["task_completion_pct"])
        page = render(self.c, 1, "one")
        self.assertIn("N/A (no closed leads)", page)
        self.assertNotIn("<img", page)
        self.assertIn("Distinct leads reporting payments", page)

    def test_decimal_money_large_amount(self):
        self.assertEqual(_money(123456789012345678), "$1,234,567,890,123,456.78")

    @patch("revenue_attribution_v34.bos.core.access", side_effect=ValueError("Denied"))
    def test_denied(self, access):
        with self.assertRaises(ValueError):
            analyze(self.c, 1, "two")


if __name__ == "__main__":
    unittest.main()
