import sqlite3
import unittest
from unittest.mock import patch
from revenue_command_v25 import snapshot, render


class RevenueCommandTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE bos59_actions (workspace_id TEXT,decision TEXT)")
        self.c.execute("CREATE TABLE bos59_leads (workspace_id TEXT,id TEXT,name TEXT)")
        self.c.execute("CREATE TABLE vx_followup23 (workspace_id TEXT,lead_id TEXT,status TEXT,due_date TEXT,created INTEGER)")
        self.c.executemany("INSERT INTO bos59_actions VALUES (?,?)",[
            ("one","pending"),("one","approved"),("two","pending")])
        self.c.executemany("INSERT INTO bos59_leads VALUES (?,?,?)",[
            ("one","a","Client A"),("two","b","Client B")])
        self.c.executemany("INSERT INTO vx_followup23 VALUES (?,?,?,?,?)",[
            ("one","a","planned","2026-12-01",1),
            ("two","b","planned","2026-11-01",1)])
    def tearDown(self):
        self.c.close()

    @patch("revenue_command_v25.priorities.live_rankings",return_value=[])
    @patch("revenue_command_v25.conversion.summarize")
    @patch("revenue_command_v25.bos.core.access")
    def test_workspace_scope(self,access,summarize,rankings):
        summarize.return_value={"open_leads":1,"potential_open_value":100,
                                "closed_win_rate":None,"overdue_followups":0}
        data=snapshot(self.c,7,"one")
        self.assertEqual(data["pending_approvals"],1)
        self.assertEqual(data["next_followups"],[("2026-12-01","Client A","planned")])
        access.assert_called_once_with(self.c,7,"one")
        page=render(self.c,7,"one")
        self.assertIn("Client A",page)
        self.assertNotIn("Client B",page)

    @patch("revenue_command_v25.bos.core.access",side_effect=ValueError("Access denied"))
    def test_access_denied(self,access):
        with self.assertRaises(ValueError):
            snapshot(self.c,7,"two")


if __name__=="__main__":
    unittest.main()
