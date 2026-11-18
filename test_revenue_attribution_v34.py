import sqlite3
import unittest
from unittest.mock import patch
from revenue_attribution_v34 import analyze,render

class AttributionTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE bos59_leads (id TEXT,workspace_id TEXT,source TEXT,status TEXT)")
        self.c.execute("CREATE TABLE vx_outcomes33 (workspace_id TEXT,lead_id TEXT,kind TEXT,amount_cents INTEGER)")
        self.c.execute("CREATE TABLE vx_revenue_tasks29 (workspace_id TEXT,lead_id TEXT,status TEXT)")
        self.c.executemany("INSERT INTO bos59_leads VALUES (?,?,?,?)",[
            ("a","one","Referral","won"),("b","one","Referral","new"),
            ("c","one","Web <script>","contacted"),("d","two","Referral","won")])
        self.c.executemany("INSERT INTO vx_outcomes33 VALUES (?,?,?,?)",[
            ("one","a","payment_reported",12500),("one","a","appointment_booked",0),
            ("two","d","payment_reported",999999)])
        self.c.executemany("INSERT INTO vx_revenue_tasks29 VALUES (?,?,?)",[
            ("one","a","done"),("one","b","todo"),("two","d","done")])
    def tearDown(self):self.c.close()

    @patch("revenue_attribution_v34.execution.setup")
    @patch("revenue_attribution_v34.outcomes.setup")
    @patch("revenue_attribution_v34.bos.init")
    @patch("revenue_attribution_v34.bos.core.access")
    def test_scoped_aggregation(self,access,init,setup_outcomes,setup_tasks):
        rows=analyze(self.c,1,"one")
        referral=next(r for r in rows if r["source"]=="Referral")
        self.assertEqual(referral["leads"],2)
        self.assertEqual(referral["won_share_pct"],50.0)
        self.assertEqual(referral["reported_cents"],12500)
        self.assertEqual(referral["outcomes"],2)
        self.assertEqual(referral["completed_tasks"],1)
        self.assertNotIn("<script>",render(self.c,1,"one"))
        access.assert_called_with(self.c,1,"one")

    @patch("revenue_attribution_v34.bos.core.access",side_effect=ValueError("Denied"))
    def test_denied(self,access):
        with self.assertRaises(ValueError):analyze(self.c,1,"two")

if __name__=="__main__":unittest.main()
