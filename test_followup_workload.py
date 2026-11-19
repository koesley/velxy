"""Workspace-wide follow-up workload and safe outcome regression tests."""
import sqlite3
import unittest
from datetime import date
from unittest.mock import patch
import revenue_followups_v23 as f


class FollowupWorkloadTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE bos59_leads (id TEXT, workspace_id TEXT, name TEXT, status TEXT, updated INTEGER)")
        self.db.executemany("INSERT INTO bos59_leads VALUES (?,?,?,?,?)",
                            [("a","one","<Acme>","new",1),("b","two","Other","new",1)])
        f.setup(self.db)

    def tearDown(self):
        self.db.close()

    def add(self, workspace, number, due, status="planned"):
        self.db.execute("INSERT INTO vx_followup23 VALUES (?,?,?,?,?,?,?,?,?)",
                        (str(number),workspace,"a" if workspace=="one" else "b",due,status,"",1,1,1))

    @patch("revenue_followups_v23.bos.core.access")
    def test_full_workload_beyond_display_limit_and_tenant_isolation(self, access):
        for i in range(120):
            self.add("one",i,"2026-11-18")
        for i in range(8):
            self.add("two","other"+str(i),"2026-11-18")
        counts=f.workload(self.db,1,"one",date(2026,11,19))
        self.assertEqual(counts["overdue"],120)
        self.assertEqual(counts["total"],120)
        html=f.render(self.db,1,"one","token")
        self.assertIn("120 overdue",html)
        self.assertIn("Only the first 100 records",html)
        self.assertNotIn("Other",html)
        self.assertIn("&lt;Acme&gt;",html)

    @patch("revenue_followups_v23.bos.core.access")
    def test_due_boundaries_and_completed_exclusion(self, access):
        for i,(due,status) in enumerate([
            ("2026-11-18","planned"),("2026-11-19","planned"),
            ("2026-11-20","planned"),("2026-11-26","planned"),
            ("2026-11-27","planned"),("2026-11-18","replied")]):
            self.add("one",i,due,status)
        result=f.workload(self.db,1,"one",date(2026,11,19))
        self.assertEqual(result,dict(total=6,planned=5,overdue=1,due_today=1,next_seven_days=2))

    @patch("revenue_followups_v23.bos.core.access")
    def test_empty_and_invalid_date(self, access):
        self.assertEqual(f.workload(self.db,1,"one",date(2026,11,19))["total"],0)
        with self.assertRaises(ValueError):
            f.workload(self.db,1,"one","2026-11-19")

    @patch("revenue_followups_v23.bos.core.access",side_effect=ValueError("Denied"))
    def test_access_denied(self, access):
        with self.assertRaisesRegex(ValueError,"Denied"):
            f.workload(self.db,1,"one")

    @patch("revenue_followups_v23.bos.core.access")
    def test_outcome_cannot_be_overwritten(self, access):
        self.add("one","id","2026-11-19")
        f.change_status(self.db,1,"one","id","replied")
        with self.assertRaises(ValueError):
            f.change_status(self.db,1,"one","id","won")
        self.assertEqual(self.db.execute("SELECT status FROM vx_followup23 WHERE id='id'").fetchone()[0],"replied")


if __name__ == "__main__":
    unittest.main()
