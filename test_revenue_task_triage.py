import sqlite3
import unittest
from unittest.mock import patch
from datetime import datetime
import revenue_task_triage as triage

NOW = int(datetime(2026,11,19,12,0).timestamp())

class TaskTriageTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE bos59_leads (id TEXT,workspace_id TEXT,name TEXT)")
        self.c.executemany("INSERT INTO bos59_leads VALUES (?,?,?)",
                           [("same","a","<script>alert(1)</script>"),("same","b","Secret lead"),
                            ("other","a","Other lead")])
        self.c.execute("""CREATE TABLE vx_revenue_tasks29
            (id TEXT PRIMARY KEY,workspace_id TEXT,lead_id TEXT,title TEXT,
             owner_id INTEGER,due_date TEXT,status TEXT,created INTEGER,updated INTEGER)""")
        self.c.executemany("INSERT INTO vx_revenue_tasks29 VALUES (?,?,?,?,?,?,?,?,?)",[
            ("a1","a","same","<b>Call</b>",7,"2026-11-18","todo",0,NOW-8*86400),
            ("a2","a","other","Review",8,"2026-11-25","blocked",0,NOW),
            ("a3","a","other","Due today",7,"2026-11-19","in_progress",0,NOW),
            ("a4","a","other","Stalled",7,"2026-11-25","todo",0,NOW-8*86400),
            ("a5","a","other","Done",7,"2026-11-10","done",0,NOW-8*86400),
            ("b1","b","same","Private",9,"2026-11-01","todo",0,NOW-8*86400)])
    def tearDown(self): self.c.close()

    @patch("revenue_task_triage.execution.setup")
    @patch("revenue_task_triage.bos.core.access")
    def test_priority_counts_and_workspace_isolation(self,access,setup):
        result=triage.triage(self.c,7,"a",now=NOW)
        self.assertEqual(result["counts"],{"overdue":1,"blocked":1,"stalled":2,"due_today":1})
        self.assertEqual([t["id"] for t in result["items"]],["a1","a2","a3","a4"])
        self.assertNotIn("Private",str(result))

    @patch("revenue_task_triage.execution.setup")
    @patch("revenue_task_triage.bos.core.access")
    def test_limit_and_html_escaping(self,access,setup):
        self.assertEqual(len(triage.triage(self.c,7,"a",now=NOW,limit=2)["items"]),2)
        markup=triage.render(self.c,7,"a",now=NOW)
        self.assertIn("&lt;b&gt;Call&lt;/b&gt;",markup)
        self.assertIn("&lt;script&gt;",markup)
        self.assertNotIn("Secret lead",markup)

    @patch("revenue_task_triage.execution.setup")
    @patch("revenue_task_triage.bos.core.access")
    def test_invalid_limit(self,access,setup):
        for value in (0,51,True,"10"):
            with self.assertRaises(ValueError):
                triage.triage(self.c,7,"a",now=NOW,limit=value)

    @patch("revenue_task_triage.bos.core.access",side_effect=ValueError("Denied"))
    def test_authorization_precedes_query(self,access):
        with self.assertRaisesRegex(ValueError,"Denied"):
            triage.triage(self.c,7,"a",now=NOW)

if __name__=="__main__":
    unittest.main()
