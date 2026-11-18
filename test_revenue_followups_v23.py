import sqlite3
import unittest
from unittest.mock import patch
from revenue_followups_v23 import create, change_status, setup


class FollowupTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE bos59_leads (id TEXT, workspace_id TEXT, status TEXT)")
        self.c.executemany("INSERT INTO bos59_leads VALUES (?,?,?)",
                           [("a","one","new"),("b","two","contacted"),("c","one","won")])
        setup(self.c)

    def tearDown(self):
        self.c.close()

    @patch("revenue_followups_v23.bos.core.access")
    def test_scoped_creation_and_duplicates(self, access):
        with self.assertRaises(ValueError):
            create(self.c,1,"one","b","2026-12-01","")
        with self.assertRaises(ValueError):
            create(self.c,1,"one","c","2026-12-01","")
        identifier=create(self.c,1,"one","a","2026-12-01","")
        with self.assertRaises(ValueError):
            create(self.c,1,"one","a","2026-12-01","")
        with self.assertRaises(ValueError):
            change_status(self.c,1,"two",identifier,"contacted")
        change_status(self.c,1,"one",identifier,"contacted")
        self.assertEqual(self.c.execute("SELECT status FROM vx_followup23 WHERE id=?",(identifier,)).fetchone()[0],"contacted")

    @patch("revenue_followups_v23.bos.core.access", side_effect=ValueError("Denied"))
    def test_access_failure(self, access):
        with self.assertRaises(ValueError):
            create(self.c,1,"one","a","2026-12-01","")

    @patch("revenue_followups_v23.bos.core.access")
    def test_date_and_status_validation(self, access):
        with self.assertRaises(ValueError):
            create(self.c,1,"one","a","2026-99-99","")
        identifier=create(self.c,1,"one","a","2026-12-01","")
        with self.assertRaises(ValueError):
            change_status(self.c,1,"one",identifier,"planned")


if __name__=="__main__":
    unittest.main()
