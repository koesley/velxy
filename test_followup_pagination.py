"""Regression tests for workspace-scoped follow-up pagination."""
import sqlite3
import unittest
from unittest.mock import patch
from revenue_followups_v23 import render, setup

class FollowupPaginationTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE bos59_leads (id TEXT, workspace_id TEXT, name TEXT, status TEXT, updated INTEGER)")
        setup(self.c)
        for i in range(125):
            wid = "other" if i >= 120 else "mine"
            self.c.execute("INSERT INTO bos59_leads VALUES (?,?,?,?,?)", (str(i),wid,"Lead "+str(i),"new",i))
            self.c.execute("INSERT INTO vx_followup23 VALUES (?,?,?,?,?,?,?,?,?)",
                           (str(i),wid,str(i),"2026-12-01","planned" if i%2==0 else "replied","<note>",1,i,i))
    def tearDown(self):
        self.c.close()

    @patch("revenue_followups_v23.bos.core.access")
    def test_pages_cover_all_scoped_records(self, access):
        pages=[render(self.c,1,"mine","csrf",p) for p in (1,2,3)]
        self.assertIn("Matching records: 120",pages[0])
        self.assertIn("Page 3 of 3",pages[2])
        self.assertIn("Lead 119",pages[2])
        self.assertNotIn("Lead 124",''.join(pages))
        self.assertIn("Next",pages[0])
        self.assertIn("Previous",pages[2])

    @patch("revenue_followups_v23.bos.core.access")
    def test_status_filter_and_escaping(self, access):
        page=render(self.c,1,"mine","csrf",1,"planned")
        self.assertIn("Matching records: 60",page)
        self.assertIn("&lt;note&gt;",page)
        self.assertNotIn("<note>",page)

    @patch("revenue_followups_v23.bos.core.access")
    def test_invalid_pagination_rejected(self, access):
        for page,status in [(0,"all"),(10001,"all"),(4,"all"),(1,"unknown")]:
            with self.assertRaises(ValueError):
                render(self.c,1,"mine","csrf",page,status)

    @patch("revenue_followups_v23.bos.core.access",side_effect=ValueError("Denied"))
    def test_denied_access(self, access):
        with self.assertRaises(ValueError):
            render(self.c,1,"mine","csrf")

if __name__ == "__main__":
    unittest.main()
