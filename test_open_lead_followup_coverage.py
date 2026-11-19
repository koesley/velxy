import sqlite3
import unittest
from unittest.mock import patch

from revenue_followups_v23 import setup, uncovered_open_leads, render


class OpenLeadCoverageTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        self.c.execute("""CREATE TABLE bos59_leads (
            id TEXT PRIMARY KEY, workspace_id TEXT, name TEXT, status TEXT,
            value REAL, updated INTEGER)""")
        self.c.executemany("INSERT INTO bos59_leads VALUES (?,?,?,?,?,?)", [
            ("a","one","<script>alert(1)</script>","contacted",40,1),
            ("b","one","New lead","new",10,2),
            ("c","one","Scheduled","new",20,3),
            ("d","two","Other tenant","contacted",999,0),
            ("e","one","Closed","won",50,0),
        ])
        setup(self.c)
        self.c.execute("""INSERT INTO vx_followup23 VALUES
            ('f','one','c','2026-12-01','planned','',1,1,1)""")
        self.c.execute("""INSERT INTO vx_followup23 VALUES
            ('g','one','b','2026-11-01','replied','',1,1,1)""")

    def tearDown(self):
        self.c.close()

    @patch("revenue_followups_v23.bos.core.access")
    def test_workspace_and_planned_coverage(self, access):
        count, rows = uncovered_open_leads(self.c,1,"one")
        self.assertEqual(count,2)
        self.assertEqual([r[0] for r in rows],["a","b"])
        self.assertEqual(uncovered_open_leads(self.c,1,"two")[0],1)

    @patch("revenue_followups_v23.bos.core.access")
    def test_limit_and_total(self, access):
        count, rows = uncovered_open_leads(self.c,1,"one",1)
        self.assertEqual(count,2)
        self.assertEqual(len(rows),1)
        for limit in (0,51,"1",True):
            with self.assertRaises(ValueError):
                uncovered_open_leads(self.c,1,"one",limit)

    @patch("revenue_followups_v23.bos.core.access")
    def test_render_escapes_leads_and_discloses_limits(self, access):
        # Existing tracker needs the full lead schema for its selection list.
        self.c.execute("ALTER TABLE bos59_leads ADD COLUMN contact TEXT DEFAULT ''")
        html = render(self.c,1,"one","token")
        self.assertIn("Open leads needing a follow-up plan",html)
        self.assertIn("&lt;script&gt;",html)
        self.assertNotIn("<script>",html)
        self.assertIn("not collected revenue",html)

    @patch("revenue_followups_v23.bos.core.access",side_effect=ValueError("Denied"))
    def test_denied(self, access):
        with self.assertRaises(ValueError):
            uncovered_open_leads(self.c,1,"one")


if __name__ == "__main__":
    unittest.main()
