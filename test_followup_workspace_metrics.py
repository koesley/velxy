"""Regression tests for full-workspace manual follow-up reporting."""
import sqlite3
import unittest
from unittest.mock import patch
import revenue_followups_v23 as followups


class FollowupMetricsTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE bos59_leads (id TEXT, workspace_id TEXT, status TEXT, name TEXT, updated INTEGER)")
        self.db.executemany("INSERT INTO bos59_leads VALUES (?,?,?,?,?)", [
            ("a", "one", "new", "<script>alert(1)</script>", 1),
            ("b", "two", "new", "Other tenant", 1),
        ])
        followups.setup(self.db)

    def tearDown(self):
        self.db.close()

    @patch("revenue_followups_v23.bos.core.access")
    def test_counts_beyond_preview_and_tenant_isolation(self, access):
        rows = [(str(i), "one", "a", "2026-01-01", "planned", "", 1, i, i)
                for i in range(130)]
        rows += [("other", "two", "b", "2026-01-01", "planned", "", 2, 1, 1)]
        rows += [("done", "one", "a", "2026-01-02", "won", "", 1, 1, 1)]
        self.db.executemany("INSERT INTO vx_followup23 VALUES (?,?,?,?,?,?,?,?,?)", rows)
        result = followups.metrics(self.db, 1, "one", "2026-01-03")
        self.assertEqual(result, {"planned": 130, "overdue": 130, "due_today": 0, "completed": 1})
        html = followups.render(self.db, 1, "one", "csrf")
        self.assertIn("Planned (all): 130", html)
        self.assertIn("Overdue (all): 130", html)
        self.assertIn("Showing at most 100 records", html)
        self.assertNotIn("Other tenant", html)
        self.assertNotIn("<script>", html)

    @patch("revenue_followups_v23.bos.core.access")
    def test_due_today_and_empty_workspace(self, access):
        self.assertEqual(followups.metrics(self.db, 1, "one", "2026-01-01"),
                         {"planned": 0, "overdue": 0, "due_today": 0, "completed": 0})
        self.db.execute("INSERT INTO vx_followup23 VALUES (?,?,?,?,?,?,?,?,?)",
                        ("today", "one", "a", "2026-01-01", "planned", "", 1, 1, 1))
        self.assertEqual(followups.metrics(self.db, 1, "one", "2026-01-01")["due_today"], 1)
        self.assertEqual(followups.metrics(self.db, 1, "one", "2026-01-01")["overdue"], 0)

    @patch("revenue_followups_v23.bos.core.access", side_effect=ValueError("Denied"))
    def test_authorization_failure(self, access):
        with self.assertRaisesRegex(ValueError, "Denied"):
            followups.metrics(self.db, 2, "one", "2026-01-01")


if __name__ == "__main__":
    unittest.main()
