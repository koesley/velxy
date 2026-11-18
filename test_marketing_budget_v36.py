import sqlite3
import unittest
from unittest.mock import patch
from marketing_budget_v36 import cents,set_budget,analyze,setup

class MarketingBudgetTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE bos59_leads (workspace_id TEXT,source TEXT)")
        self.c.executemany("INSERT INTO bos59_leads VALUES (?,?)",[("one","Referral"),("two","Ads")])
        setup(self.c)
    def tearDown(self):self.c.close()

    def test_money_validation(self):
        self.assertEqual(cents("12.50"),1250)
        for value in ("NaN","-1","2.001","1000000001"):
            with self.assertRaises(ValueError):cents(value)

    @patch("marketing_budget_v36.bos.init")
    @patch("marketing_budget_v36.bos.core.access")
    def test_source_validation_and_upsert(self,access,init):
        with self.assertRaises(ValueError):set_budget(self.c,1,"one","Ads","100")
        set_budget(self.c,1,"one","Referral","100")
        set_budget(self.c,1,"one","Referral","150")
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM vx_marketing_budget36").fetchone()[0],1)
        self.assertEqual(self.c.execute("SELECT budget_cents FROM vx_marketing_budget36").fetchone()[0],15000)

    @patch("marketing_budget_v36.acquisition.analyze")
    @patch("marketing_budget_v36.bos.core.access")
    def test_historical_equivalence_and_scope(self,access,history):
        self.c.executemany("INSERT INTO vx_marketing_budget36 VALUES (?,?,?,?,?)",[
            ("one","Referral",50000,1,1),("two","Ads",90000,2,1)])
        history.return_value=[{"source":"Referral","leads":10,"cost_cents":10000,
                               "cost_per_lead_cents":1000}]
        result=analyze(self.c,1,"one")
        self.assertEqual(result["total_budget_cents"],50000)
        self.assertEqual(result["channels"][0]["historical_lead_equivalent"],50.0)

    @patch("marketing_budget_v36.bos.core.access",side_effect=ValueError("Denied"))
    def test_denied(self,access):
        with self.assertRaises(ValueError):analyze(self.c,1,"two")

if __name__=="__main__":unittest.main()
