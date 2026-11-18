import sqlite3
import unittest
from unittest.mock import patch
from campaign_optimization_v39 import setup,propose,decide,analyze,money

class OptimizationTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE vx_campaign37 (id TEXT,workspace_id TEXT,name TEXT,spend_cents INTEGER,leads INTEGER,conversions INTEGER)")
        self.c.executemany("INSERT INTO vx_campaign37 VALUES (?,?,?,?,?,?)",[
            ("c1","one","Spring",10000,40,8),("c2","two","Other",100000,50,10)])
        setup(self.c)
    def tearDown(self):self.c.close()

    @patch("campaign_optimization_v39.campaigns.setup")
    @patch("campaign_optimization_v39.bos.core.access")
    def test_review_workflow_and_isolation(self,access,init):
        with self.assertRaises(ValueError):
            propose(self.c,1,"one","c2","Variant","New copy","Better","CPL","20","50")
        identifier=propose(self.c,1,"one","c1","Variant","New copy","Better","CPL","20","50")
        with self.assertRaises(ValueError):
            decide(self.c,1,"one",identifier,"approved","Looks good")
        with self.assertRaises(ValueError):
            decide(self.c,2,"two",identifier,"approved","Looks good")
        with self.assertRaises(ValueError):
            decide(self.c,2,"one",identifier,"implemented","Done")
        decide(self.c,2,"one",identifier,"approved","Test with a capped budget")
        with self.assertRaises(ValueError):
            decide(self.c,2,"one",identifier,"approved","Again")
        decide(self.c,1,"one",identifier,"implemented","Manual change applied")
        self.assertEqual(analyze(self.c,1,"one")[0]["status"],"implemented")
        self.assertEqual(analyze(self.c,1,"two"),[])

    def test_budget(self):
        self.assertEqual(money("50.25"),5025)
        for value in ("NaN","-5","0.001"):
            with self.assertRaises(ValueError):money(value)

    @patch("campaign_optimization_v39.bos.core.access",side_effect=ValueError("Denied"))
    def test_denied(self,access):
        with self.assertRaises(ValueError):analyze(self.c,1,"two")

if __name__=="__main__":unittest.main()
