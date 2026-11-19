import sqlite3
import unittest
from unittest.mock import patch
from acquisition_intelligence_v35 import add,analyze,setup,expense_history,render

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


    @patch("acquisition_intelligence_v35.bos.core.access")
    def test_expense_history_tenant_and_order(self,access):
        from datetime import datetime,timezone
        now=int(datetime(2026,11,19,tzinfo=timezone.utc).timestamp())
        self.c.executemany("INSERT INTO vx_acquisition_cost35 VALUES (?,?,?,?,?,?,?)",[
            ("a","one","Referral",1234,"First",1,now-60),
            ("b","one","Referral",500,"Second",1,now-30),
            ("c","two","Referral",999999,"Other tenant",2,now-10)])
        history=expense_history(self.c,1,"one",now=now)
        self.assertEqual([r["id"] for r in history["recent"]],["b","a"])
        self.assertEqual(history["months"][-1]["cost_cents"],1734)
        self.assertEqual(len(history["months"]),6)

    @patch("acquisition_intelligence_v35.bos.core.access")
    def test_utc_month_boundary_and_future_exclusion(self,access):
        from datetime import datetime,timezone
        stamp=lambda y,m,d:int(datetime(y,m,d,tzinfo=timezone.utc).timestamp())
        now=stamp(2026,1,2)
        self.c.executemany("INSERT INTO vx_acquisition_cost35 VALUES (?,?,?,?,?,?,?)",[
            ("old","one","Referral",100,"",1,stamp(2025,12,31)),
            ("new","one","Referral",200,"",1,stamp(2026,1,1)),
            ("future","one","Referral",900,"",1,stamp(2026,2,1))])
        months=expense_history(self.c,1,"one",now=now)["months"]
        self.assertEqual(months[-2:],[
            {"month":"2025-12","cost_cents":100},
            {"month":"2026-01","cost_cents":200}])

    @patch("acquisition_intelligence_v35.bos.core.access")
    def test_history_limit_validation(self,access):
        for bad in (0,-1,101,True,"20"):
            with self.assertRaises(ValueError):
                expense_history(self.c,1,"one",limit=bad)

    @patch("acquisition_intelligence_v35.bos.init")
    @patch("acquisition_intelligence_v35.bos.core.access")
    def test_control_characters_rejected(self,access,init):
        with self.assertRaises(ValueError):
            add(self.c,1,"one","Referral"+chr(10)+"Fake","10","")
        with self.assertRaises(ValueError):
            add(self.c,1,"one","Referral","10","bad"+chr(0)+"note")

    @patch("acquisition_intelligence_v35.attribution.analyze")
    @patch("acquisition_intelligence_v35.bos.init")
    @patch("acquisition_intelligence_v35.bos.core.access")
    def test_render_escapes_audit_entries(self,access,init,attribution):
        self.c.execute("INSERT INTO vx_acquisition_cost35 VALUES (?,?,?,?,?,?,?)",
                       ("a","one","Referral",150,"<script>alert(1)</script>",1,1))
        attribution.return_value=[{"source":"Referral","leads":1,"won_leads":0,"reported_cents":0}]
        page=render(self.c,1,"one","csrf")
        self.assertIn("&lt;script&gt;",page)
        self.assertNotIn("<script>",page)
        self.assertIn("Recorded spending by month",page)

if __name__=="__main__":unittest.main()
