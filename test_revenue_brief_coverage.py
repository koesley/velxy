"""Regression tests for workspace-scoped daily brief coverage and workload."""
import sqlite3
import unittest
from unittest.mock import patch
import revenue_brief_v26 as brief


class DailyBriefCoverageTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript("""
            CREATE TABLE bos59_leads(id TEXT, workspace_id TEXT, status TEXT);
            CREATE TABLE vx_followup23(id TEXT, lead_id TEXT, workspace_id TEXT,
                                       status TEXT, due_date TEXT);
            CREATE TABLE bos59_actions(workspace_id TEXT, decision TEXT);
        """)
        self.db.executemany("INSERT INTO bos59_leads VALUES(?,?,?)", [
            ("a","one","new"),("b","one","contacted"),("c","one","won"),
            ("foreign","two","new")])
        self.db.executemany("INSERT INTO vx_followup23 VALUES(?,?,?,?,?)", [
            ("f1","a","one","contacted","2026-01-01"),
            ("f2","c","one","planned","2026-01-01"),
            ("f3","foreign","two","planned","2026-01-01")])
        self.access = patch.object(brief.bos.core, "access").start()
        self.metrics = patch.object(brief.conversion, "summarize", return_value={}).start()
        self.addCleanup(patch.stopall)

    def tearDown(self):
        self.db.close()

    def test_completed_activity_does_not_cover_open_lead(self):
        result = brief.build(self.db, 1, "one")
        self.assertTrue(any("2 open lead(s)" in a["detail"] for a in result["actions"]))

    def test_planned_activity_covers_only_its_open_lead(self):
        self.db.execute("INSERT INTO vx_followup23 VALUES(?,?,?,?,?)",
                        ("f4","a","one","planned","2026-12-01"))
        result = brief.build(self.db, 1, "one")
        self.assertTrue(any("1 open lead(s)" in a["detail"] for a in result["actions"]))

    def test_upcoming_window_excludes_today_and_day_eight(self):
        from datetime import date, timedelta
        today = date.today()
        for i, days in enumerate((0,1,7,8)):
            self.db.execute("INSERT INTO vx_followup23 VALUES(?,?,?,?,?)",
                            (str(i),"b","one","planned",
                             (today+timedelta(days=days)).isoformat()))
        result = brief.build(self.db, 1, "one")
        self.assertTrue(any("2 follow-up(s) are due" in a["detail"]
                            for a in result["actions"]))

    def test_denied_access_stops_queries(self):
        self.access.side_effect = PermissionError("denied")
        with self.assertRaises(PermissionError):
            brief.build(self.db, 1, "one")
        self.metrics.assert_not_called()

    def test_render_escapes_workspace_in_links(self):
        result = brief.render(self.db, 1, "one")
        self.assertIn("Daily Revenue Action Brief", result)
        self.assertIn("Plan next steps", result)
        self.assertIn("contact eligibility", result)


if __name__ == "__main__":
    unittest.main()
