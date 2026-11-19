import sqlite3
import unittest
from datetime import date, timedelta
from unittest.mock import patch
import revenue_conversion_v24 as conversion

class FollowupHealthTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE bos59_leads (workspace_id TEXT,status TEXT,value REAL)")
        self.db.execute("CREATE TABLE vx_followup23 (workspace_id TEXT,status TEXT,due_date TEXT)")
        self.patches = [patch("revenue_conversion_v24.bos.core.access"),
                        patch("revenue_conversion_v24.bos.init"),
                        patch("revenue_conversion_v24.followups.setup")]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.db.close()

    def test_due_windows_and_tenant_scope(self):
        today = date.today()
        rows = [
            ("one", "planned", (today - timedelta(days=1)).isoformat()),
            ("one", "planned", today.isoformat()),
            ("one", "planned", (today + timedelta(days=7)).isoformat()),
            ("one", "planned", (today + timedelta(days=8)).isoformat()),
            ("one", "replied", today.isoformat()),
            ("two", "planned", (today - timedelta(days=5)).isoformat()),
            ("two", "replied", today.isoformat())]
        self.db.executemany("INSERT INTO vx_followup23 VALUES (?,?,?)", rows)
        data = conversion.summarize(self.db, 1, "one")
        self.assertEqual(data["overdue_followups"], 1)
        self.assertEqual(data["due_next_7_days"], 2)
        self.assertEqual(data["replied_followups"], 1)
        self.assertEqual(data["reply_share"], 20.0)

    def test_empty_workspace(self):
        data = conversion.summarize(self.db, 1, "one")
        self.assertEqual(data["due_next_7_days"], 0)
        self.assertIsNone(data["reply_share"])

    def test_render_is_read_only(self):
        self.db.execute("INSERT INTO vx_followup23 VALUES (?,?,?)",
                        ("one", "replied", date.today().isoformat()))
        before = self.db.total_changes
        html = conversion.render(self.db, 1, "one")
        self.assertIn("Share marked replied", html)
        self.assertIn("not an email deliverability rate", html)
        self.assertEqual(self.db.total_changes, before)

    def test_access_denied(self):
        with patch("revenue_conversion_v24.bos.core.access", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                conversion.summarize(self.db, 1, "two")

if __name__ == "__main__":
    unittest.main()
