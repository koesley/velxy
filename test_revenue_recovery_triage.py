"""Regression coverage for recovery workload triage."""
import sqlite3
import unittest
from datetime import datetime
from unittest.mock import patch

import revenue_recovery_v31 as recovery


class RecoveryWorkloadTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE bos59_leads (workspace_id TEXT,id TEXT,name TEXT)")
        self.c.execute("""CREATE TABLE vx_revenue_tasks29 (
            id TEXT,workspace_id TEXT,lead_id TEXT,title TEXT,status TEXT,
            due_date TEXT,updated INTEGER,owner_id INTEGER,created INTEGER)""")
        self.c.executemany("INSERT INTO bos59_leads VALUES (?,?,?)",
                           [("one","l","<Lead & Co>"),("two","l","Other")])
        recovery.setup(self.c)
        self.now = int(datetime(2026,11,19,12).timestamp())

    def tearDown(self):
        self.c.close()

    def task(self, identifier, wid="one", status="blocked", due="2026-11-01", updated=1):
        self.c.execute("INSERT INTO vx_revenue_tasks29 VALUES (?,?,?,?,?,?,?,?,?)",
                       (identifier,wid,"l","Task "+identifier,status,due,updated,7,1))

    @patch("revenue_recovery_v31.bos.core.access")
    def test_full_workspace_counts_and_bounded_priority_queue(self, access):
        for i in range(135):
            self.task("t%03d" % i)
        self.task("other",wid="two")
        data = recovery.workload(self.c,7,"one",now=self.now)
        self.assertEqual(data["total"],135)
        self.assertEqual(len(data["items"]),100)
        self.assertEqual(data["items"][0]["id"],"t000")
        self.assertTrue(all(x["id"]!="other" for x in data["items"]))

    @patch("revenue_recovery_v31.bos.core.access")
    def test_eligible_reasons_and_completed_exclusion(self, access):
        self.task("blocked",status="blocked",due="2026-12-01",updated=self.now)
        self.task("overdue",status="todo",due="2026-11-01",updated=self.now)
        self.task("stalled",status="in_progress",due="2026-12-01",updated=self.now-8*86400)
        self.task("fine",status="todo",due="2026-12-01",updated=self.now)
        self.task("done",status="done")
        data = recovery.workload(self.c,7,"one",now=self.now)
        self.assertEqual(data["total"],3)
        self.assertEqual({x["id"] for x in data["items"]},{"blocked","overdue","stalled"})

    @patch("revenue_recovery_v31.bos.core.access")
    def test_active_plan_prevents_duplicate_form(self, access):
        self.task("t")
        self.c.execute("INSERT INTO vx_recovery31 VALUES (?,?,?,?,?,?,?,?,?)",
                       ("r","one","t",7,"Blocked","Call","active",1,1))
        data = recovery.workload(self.c,7,"one",now=self.now)
        self.assertEqual(data["active_plans"],1)
        self.assertTrue(data["items"][0]["has_active_plan"])
        page = recovery.render(self.c,7,"one","csrf")
        self.assertIn("Active recovery plan already recorded",page)
        self.assertNotIn('name="action" value="create"',page)
        self.assertIn("&lt;Lead &amp; Co&gt;",page)

    @patch("revenue_recovery_v31.bos.core.access",side_effect=ValueError("Denied"))
    def test_denied_access(self, access):
        with self.assertRaises(ValueError):
            recovery.workload(self.c,7,"one",now=self.now)


if __name__ == "__main__":
    unittest.main()
