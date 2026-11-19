"""Regression tests for owner-scoped sales stage history."""
import sqlite3
import unittest
import sales_pipeline


class StageHistoryTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        sales_pipeline.setup(self.db)

    def tearDown(self):
        self.db.close()

    def test_create_and_transition(self):
        lead = sales_pipeline.save(self.db, 1, {"business": "Example Cafe", "stage": "new"})
        sales_pipeline.save(self.db, 1, {"lead_id": lead, "business": "Example Cafe", "stage": "meeting"})
        rows = sales_pipeline.lead_history(self.db, 1, lead)
        self.assertEqual([(r[0], r[1]) for r in rows], [("new", "meeting"), (None, "new")])

    def test_unchanged_stage_does_not_duplicate(self):
        lead = sales_pipeline.save(self.db, 1, {"business": "Example Cafe"})
        sales_pipeline.save(self.db, 1, {"lead_id": lead, "business": "Example Cafe", "notes": "Updated"})
        self.assertEqual(len(sales_pipeline.lead_history(self.db, 1, lead)), 1)

    def test_cross_owner_cannot_read_or_write_history(self):
        lead = sales_pipeline.save(self.db, 1, {"business": "Example Cafe"})
        self.assertEqual(sales_pipeline.lead_history(self.db, 2, lead), [])
        with self.assertRaises(ValueError):
            sales_pipeline.save(self.db, 2, {"lead_id": lead, "business": "Example Cafe", "stage": "won"})
        self.assertEqual(len(sales_pipeline.lead_history(self.db, 1, lead)), 1)

    def test_history_is_escaped_in_dashboard(self):
        lead = sales_pipeline.save(self.db, 1, {"business": "<script>alert(1)</script>"})
        output = sales_pipeline.dashboard(self.db, 1, "csrf")
        self.assertIn("Stage history", output)
        self.assertNotIn("<script>", output)
        self.assertIn("&lt;script&gt;", output)

    def test_legacy_lead_has_empty_history(self):
        self.db.execute("INSERT INTO sales_pipeline_leads VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        ("legacy", 1, "Legacy Cafe", "", "", "", "new", 0, "", 1, 1))
        self.assertEqual(sales_pipeline.lead_history(self.db, 1, "legacy"), [])
        self.assertIn("Legacy Cafe", sales_pipeline.dashboard(self.db, 1, "csrf"))

    def test_limit_validation(self):
        lead = sales_pipeline.save(self.db, 1, {"business": "Example Cafe"})
        for limit in (0, -1, 101, True, "5"):
            with self.assertRaises(ValueError):
                sales_pipeline.lead_history(self.db, 1, lead, limit)


if __name__ == "__main__":
    unittest.main()
