"""Regression coverage for manually recorded follow-up cohorts."""
import sqlite3
import unittest
from unittest.mock import patch

import revenue_conversion_v24 as conversion


class FollowupCohortTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE bos59_leads (id TEXT, workspace_id TEXT, status TEXT, value REAL)")
        self.db.executemany("INSERT INTO bos59_leads VALUES (?,?,?,?)", [
            ("a", "one", "won", 100), ("b", "one", "lost", 40),
            ("c", "one", "new", 60), ("d", "one", "won", 50),
            ("foreign", "two", "won", 9000),
        ])
        self.db.execute("""CREATE TABLE vx_followup23 (
            id TEXT PRIMARY KEY, workspace_id TEXT, lead_id TEXT,
            due_date TEXT, status TEXT, note TEXT,
            created_by INTEGER, created INTEGER, updated INTEGER)""")
        self.db.executemany("INSERT INTO vx_followup23 VALUES (?,?,?,?,?,?,?,?,?)", [
            ("f1", "one", "a", "2026-11-01", "replied", "", 1, 1, 1),
            ("f2", "one", "a", "2026-11-02", "won", "", 1, 1, 1),
            ("f3", "one", "c", "2026-11-03", "planned", "", 1, 1, 1),
            ("f4", "two", "foreign", "2026-11-01", "won", "", 2, 1, 1),
        ])
        self.access = patch("revenue_conversion_v24.bos.core.access")
        self.init = patch("revenue_conversion_v24.bos.init")
        self.setup = patch("revenue_conversion_v24.followups.setup")
        self.access.start()
        self.init.start()
        self.setup.start()

    def tearDown(self):
        self.setup.stop()
        self.init.stop()
        self.access.stop()
        self.db.close()

    def test_deduplicates_multiple_followups_and_excludes_other_tenants(self):
        result = conversion.summarize(self.db, 1, "one")
        self.assertEqual(result["followup_cohorts"]["with_followup"],
                         {"open": 1, "won": 1, "lost": 0})
        self.assertEqual(result["followup_cohorts"]["without_followup"],
                         {"open": 0, "won": 1, "lost": 1})
        self.assertEqual(result["recorded_outcomes"], {"replied": 1, "won": 1})
        self.assertEqual(result["total_leads"], 4)

    def test_dashboard_discloses_noncausal_manual_reporting(self):
        page = conversion.render(self.db, 1, "one")
        self.assertIn("does not establish", page)
        self.assertIn("At least one follow-up", page)
        self.assertIn("No recorded follow-up", page)
        self.assertIn("100.0%", page)
        self.assertIn("50.0%", page)

    def test_no_closed_leads_has_na_rate(self):
        self.db.execute("DELETE FROM bos59_leads WHERE workspace_id='one'")
        self.db.execute("INSERT INTO bos59_leads VALUES ('x','one','new',0)")
        self.assertIn("N/A", conversion.render(self.db, 1, "one"))

    def test_access_denial_prevents_queries(self):
        with patch("revenue_conversion_v24.bos.core.access", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                conversion.summarize(self.db, 1, "one")


if __name__ == "__main__":
    unittest.main()
