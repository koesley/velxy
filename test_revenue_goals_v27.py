import sqlite3
import unittest
from decimal import Decimal
from unittest.mock import patch
from revenue_goals_v27 import set_goal,snapshot

class RevenueGoalsTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE bos59_leads (workspace_id TEXT,status TEXT,value REAL)")
        self.c.executemany("INSERT INTO bos59_leads VALUES (?,?,?)",[
            ("one","won",250),("one","new",100),("two","won",100000)])
    def tearDown(self):self.c.close()

    @patch("revenue_goals_v27.bos.core.access")
    def test_progress_is_scoped_and_persistent(self,access):
        set_goal(self.c,3,"one","1000.00")
        data=snapshot(self.c,3,"one")
        self.assertEqual(str(data["target"]),"1000")
        self.assertEqual(data["progress_pct"],25.0)
        self.assertEqual(data["gap"],Decimal("750"))
        self.assertEqual(str(data["open_potential"]),"100.0")
        with self.assertRaises(ValueError):set_goal(self.c,3,"one","NaN")
        with self.assertRaises(ValueError):set_goal(self.c,3,"one","10.123")

    @patch("revenue_goals_v27.bos.core.access",side_effect=ValueError("Forbidden"))
    def test_access_denied(self,access):
        with self.assertRaises(ValueError):snapshot(self.c,3,"two")

if __name__=="__main__":unittest.main()
