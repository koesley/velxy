"""Regression coverage for live lead state and safe manual follow-up outcomes."""
import sqlite3
import unittest
from unittest.mock import patch
import revenue_followups_v23 as followups


class LiveLeadSafetyTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        self.c.execute("""CREATE TABLE bos59_leads
            (id TEXT, workspace_id TEXT, status TEXT, name TEXT, updated INTEGER)""")
        self.c.executemany("INSERT INTO bos59_leads VALUES (?,?,?,?,?)", [
            ("open", "one", "new", "Open <lead>", 1),
            ("closed", "one", "won", "Closed", 1),
            ("other", "two", "new", "Other", 1),
        ])
        followups.setup(self.c)
        self.access = patch("revenue_followups_v23.bos.core.access")
        self.access.start()

    def tearDown(self):
        self.access.stop()
        self.c.close()

    def test_closing_lead_blocks_outcome_and_preserves_plan(self):
        identifier = followups.create(self.c, 1, "one", "open", "2026-12-01", "Call")
        self.c.execute("UPDATE bos59_leads SET status='won' WHERE id='open'")
        with self.assertRaisesRegex(ValueError, "no longer open"):
            followups.change_status(self.c, 1, "one", identifier, "contacted")
        self.assertEqual(self.c.execute("SELECT status FROM vx_followup23 WHERE id=?",
                                        (identifier,)).fetchone()[0], "planned")
        page = followups.render(self.c, 1, "one", "csrf")
        self.assertIn("Outcome editing is disabled", page)
        self.assertNotIn('name="action" value="status"', page)

    def test_open_lead_remains_editable(self):
        identifier = followups.create(self.c, 1, "one", "open", "2026-12-01", "Call")
        self.assertIn('name="action" value="status"', followups.render(self.c, 1, "one", "csrf"))
        followups.change_status(self.c, 1, "one", identifier, "replied")
        self.assertEqual(self.c.execute("SELECT status FROM vx_followup23 WHERE id=?",
                                        (identifier,)).fetchone()[0], "replied")

    def test_cross_workspace_outcome_denied(self):
        identifier = followups.create(self.c, 1, "one", "open", "2026-12-01", "")
        with self.assertRaises(ValueError):
            followups.change_status(self.c, 2, "two", identifier, "won")

    def test_control_characters_rejected(self):
        with self.assertRaisesRegex(ValueError, "500 characters"):
            followups.create(self.c, 1, "one", "open", "2026-12-01", "hello\\x00")
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM vx_followup23").fetchone()[0], 0)

    def test_escaped_customer_name(self):
        followups.create(self.c, 1, "one", "open", "2026-12-01", "")
        page = followups.render(self.c, 1, "one", "csrf")
        self.assertIn("Open &lt;lead&gt;", page)
        self.assertNotIn("Open <lead>", page)


if __name__ == "__main__":
    unittest.main()
