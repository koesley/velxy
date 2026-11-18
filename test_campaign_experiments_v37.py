import sqlite3
import unittest
from unittest.mock import patch
from campaign_experiments_v37 import create,update,analyze,setup,amount_cents

class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE bos59_leads (workspace_id TEXT,source TEXT)")
        self.c.executemany("INSERT INTO bos59_leads VALUES (?,?)",[("one","Referral"),("two","Ads")])
        setup(self.c)
    def tearDown(self):self.c.close()

    @patch("campaign_experiments_v37.bos.init")
    @patch("campaign_experiments_v37.bos.core.access")
    def test_campaign_lifecycle(self,access,init):
        with self.assertRaises(ValueError):
            create(self.c,1,"one","Test","Ads","Hypothesis","2026-11-01","2026-12-01")
        with self.assertRaises(ValueError):
            create(self.c,1,"one","Test","Referral","Hypothesis","2026-12-01","2026-11-01")
        identifier=create(self.c,1,"one","Test","Referral","Hypothesis","2026-11-01","2026-12-01")
        with self.assertRaises(ValueError):
            update(self.c,2,"one",identifier,"running","50",10,2,"")
        with self.assertRaises(ValueError):
            update(self.c,1,"two",identifier,"running","50",10,2,"")
        with self.assertRaises(ValueError):
            update(self.c,1,"one",identifier,"running","50",2,3,"")
        update(self.c,1,"one",identifier,"running","50.50",10,2,"A/B test")
        row=analyze(self.c,1,"one")[0]
        self.assertEqual(row["spend_cents"],5050)
        self.assertEqual(row["conversion_pct"],20.0)
        self.assertEqual(analyze(self.c,1,"two"),[])

    def test_money(self):
        self.assertEqual(amount_cents("10.25"),1025)
        for value in ("NaN","-1","1.001"):
            with self.assertRaises(ValueError):amount_cents(value)

    @patch("campaign_experiments_v37.bos.core.access",side_effect=ValueError("Denied"))
    def test_authorization(self,access):
        with self.assertRaises(ValueError):analyze(self.c,1,"two")

if __name__=="__main__":unittest.main()
