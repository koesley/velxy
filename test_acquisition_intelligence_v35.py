import sqlite3
import unittest
from unittest.mock import patch
from acquisition_intelligence_v35 import add,analyze,setup

class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE bos59_leads (workspace_id TEXT,source TEXT)")
        self.c.executemany("INSERT INTO bos59_leads VALUES (?,?)",[("one","Referral"),("two","Referral")])
        setup(self.c)
    def tearDown(self):self.c.close()

    @patch("acquisition_intelligence_v35.bos.init")
    @patch("acquisition_intelligence_v35.bos.core.access")
    def test_expense_validation(self,access,init):
        with self.assertRaises(ValueError):add(self.c,1,"one","Unknown","20","")
        with self.assertRaises(ValueError):add(self.c,1,"one","Referral","NaN","")
        with self.assertRaises(ValueError):add(self.c,1,"one","Referral","0","")
        add(self.c,1,"one","Referral","75.25","Ad campaign")
        self.assertEqual(self.c.execute("SELECT amount_cents FROM vx_acquisition_cost35").fetchone()[0],7525)

    @patch("acquisition_intelligence_v35.attribution.analyze")
    @patch("acquisition_intelligence_v35.bos.core.access")
    def test_scoped_efficiency(self,access,attribution):
        self.c.executemany("INSERT INTO vx_acquisition_cost35 VALUES (?,?,?,?,?,?,?)",[
            ("a","one","Referral",10000,"",1,1),("b","two","Referral",90000,"",2,1)])
        attribution.return_value=[{"source":"Referral","leads":5,"won_leads":2,"reported_cents":15000}]
        result=analyze(self.c,1,"one")[0]
        self.assertEqual(result["cost_cents"],10000)
        self.assertEqual(result["cost_per_lead_cents"],2000)
        self.assertEqual(result["cost_per_won_lead_cents"],5000)
        self.assertEqual(result["reported_payment_to_cost"],1.5)

    @patch("acquisition_intelligence_v35.bos.core.access",side_effect=ValueError("Denied"))
    def test_denied(self,access):
        with self.assertRaises(ValueError):analyze(self.c,1,"two")

if __name__=="__main__":unittest.main()
