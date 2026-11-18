import sqlite3
import unittest
from unittest.mock import patch
from revenue_conversion_v24 import summarize

class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE bos59_leads (workspace_id TEXT,status TEXT,value REAL)")
        self.c.executemany("INSERT INTO bos59_leads VALUES (?,?,?)",[
            ("one","new",100),("one","won",300),("one","lost",200),
            ("two","won",999999)])
        self.c.execute("CREATE TABLE vx_followup23 (workspace_id TEXT,status TEXT,due_date TEXT)")
        self.c.executemany("INSERT INTO vx_followup23 VALUES (?,?,?)",[
            ("one","planned","2000-01-01"),("one","replied","2000-01-01"),
            ("two","planned","2000-01-01")])

    def tearDown(self):
        self.c.close()

    @patch("revenue_conversion_v24.followups.setup")
    @patch("revenue_conversion_v24.bos.init")
    @patch("revenue_conversion_v24.bos.core.access")
    def test_scoped_aggregate(self,access,init,setup):
        data=summarize(self.c,3,"one")
        self.assertEqual(data["total_leads"],3)
        self.assertEqual(data["won_leads"],1)
        self.assertEqual(data["closed_win_rate"],50.0)
        self.assertEqual(data["potential_open_value"],100.0)
        self.assertEqual(data["won_marked_value"],300.0)
        self.assertEqual(data["overdue_followups"],1)
        access.assert_called_once_with(self.c,3,"one")

    @patch("revenue_conversion_v24.bos.core.access",side_effect=ValueError("Forbidden"))
    def test_access_denied(self,access):
        with self.assertRaises(ValueError):
            summarize(self.c,3,"two")

if __name__=="__main__":
    unittest.main()
