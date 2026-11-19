"""Regression checks for workspace-scoped revenue command data readiness."""
import sqlite3
import unittest
from unittest.mock import patch
import revenue_command_v25 as command


class ContactReadinessTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("""CREATE TABLE bos59_leads (
            id TEXT, workspace_id TEXT, name TEXT, contact TEXT, source TEXT,
            status TEXT, updated INTEGER)""")
        self.db.execute("CREATE TABLE bos59_actions(workspace_id TEXT,decision TEXT)")
        self.db.execute("""CREATE TABLE vx_followup23(
            workspace_id TEXT,lead_id TEXT,due_date TEXT,status TEXT,created INTEGER)""")
        self.db.executemany("INSERT INTO bos59_leads VALUES (?,?,?,?,?,?,?)",[
            ("1","mine","<script>alert(1)</script>","","","new",1),
            ("2","mine","Valid","contact@example.com","Referral","contacted",2),
            ("3","other","Other","","","new",0),
            ("4","mine","Closed","","","won",0),
        ])
        self.access=patch.object(command.bos.core,"access")
        self.summary=patch.object(command.conversion,"summarize",return_value={
            "closed_win_rate":None,"open_leads":2,"potential_open_value":0,
            "overdue_followups":0})
        self.rank=patch.object(command.priorities,"live_rankings",return_value=[])
        self.access.start();self.summary.start();self.rank.start()

    def tearDown(self):
        self.rank.stop();self.summary.stop();self.access.stop()
        self.db.close()

    def test_workspace_and_open_stage_only(self):
        d=command.snapshot(self.db,7,"mine")["contact_readiness"]
        self.assertEqual((d["open"],d["missing_contact"],d["missing_source"]),(2,1,1))
        self.assertEqual(len(d["examples"]),1)
        self.assertEqual(d["examples"][0][0],"1")

    def test_render_escapes_customer_content_and_has_no_outbound_form(self):
        page=command.render(self.db,7,"mine")
        self.assertNotIn("<script>",page)
        self.assertIn("&lt;script&gt;",page)
        self.assertIn("Verify consent",page)
        self.assertNotIn('method="post"',page)

    def test_empty_workspace(self):
        d=command.snapshot(self.db,7,"empty")["contact_readiness"]
        self.assertEqual(d["open"],0)
        self.assertEqual(d["examples"],[])

    def test_denied_access_precedes_workspace_queries(self):
        with patch.object(command.bos.core,"access",side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                command.snapshot(self.db,7,"other")


if __name__=="__main__":
    unittest.main()
