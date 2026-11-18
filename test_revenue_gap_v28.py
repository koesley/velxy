import sqlite3
import unittest
from decimal import Decimal
from unittest.mock import patch
from revenue_gap_v28 import plan,render

def opportunity(value, score):
    return {"estimated_value":str(value),"priority_score":score,
            "title":"Lead","evidence":"Entered estimate"}

class RevenueGapTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
    def tearDown(self):
        self.c.close()

    @patch("revenue_gap_v28.priorities.live_rankings")
    @patch("revenue_gap_v28.goals.snapshot")
    @patch("revenue_gap_v28.bos.core.access")
    def test_gap_coverage_and_order(self,access,goal,ranked):
        goal.return_value={"target":Decimal(1000),"won_marked":Decimal(300),
                           "gap":Decimal(700)}
        ranked.return_value=[opportunity(400,90),opportunity(350,80),opportunity(100,70)]
        result=plan(self.c,1,"one")
        self.assertEqual(result["covered"],Decimal(750))
        self.assertEqual(result["remaining"],Decimal(0))
        self.assertEqual(len(result["candidates"]),2)
        self.assertIn("Selected opportunity potential",render(self.c,1,"one"))
        access.assert_called_with(self.c,1,"one")

    @patch("revenue_gap_v28.priorities.live_rankings",return_value=[])
    @patch("revenue_gap_v28.goals.snapshot",return_value={"target":None,"gap":None})
    @patch("revenue_gap_v28.bos.core.access")
    def test_no_goal(self,access,goal,ranked):
        self.assertIsNone(plan(self.c,1,"one")["remaining"])
        self.assertIn("Set a cumulative pipeline goal",render(self.c,1,"one"))

    @patch("revenue_gap_v28.bos.core.access",side_effect=ValueError("Denied"))
    def test_access_denied(self,access):
        with self.assertRaises(ValueError):plan(self.c,1,"two")

if __name__=="__main__":
    unittest.main()
