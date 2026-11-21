import sqlite3
import unittest
import sales_pipeline
import sovereign_ascension as asc
import ascension_recovery as recovery
import ascension_command_center as center

class CommandCenterTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
    def tearDown(self):
        self.c.close()
    def test_empty_customer(self):
        s=center.snapshot(self.c,1)
        self.assertEqual(sum(s["stages"].values()),0)
        self.assertEqual(s["reported_cents"],0)
        self.assertIn("Revenue Command Center",center.dashboard(self.c,1))
    def test_tenant_isolation(self):
        sales_pipeline.save(self.c,1,{"business":"Example","stage":"proposal","value":"500"})
        self.assertEqual(center.snapshot(self.c,1)["stages"]["proposal"],1)
        self.assertEqual(center.snapshot(self.c,2)["stages"],{})
    def test_reported_money_not_verified(self):
        lid=sales_pipeline.save(self.c,1,{"business":"Example","stage":"proposal"})
        import time
        self.c.execute("UPDATE sales_pipeline_leads SET updated_at=? WHERE id=?", (int(time.time())-8*86400, lid))
        aid=asc.action(self.c,1,lid,"stalled_deal","approved")
        asc.action(self.c,1,lid,"stalled_deal","completed","Manual contact")
        recovery.record(self.c,1,aid,"payment_reported","125.50","Customer said paid in email")
        self.assertEqual(center.snapshot(self.c,1)["reported_cents"],12550)
        self.assertEqual(center.snapshot(self.c,2)["reported_cents"],0)
        self.assertIn("unverified",center.dashboard(self.c,1))
    def test_html_escapes_business_data(self):
        sales_pipeline.save(self.c,1,{"business":"<script>bad</script>","stage":"new"})
        page=center.dashboard(self.c,1)
        self.assertNotIn("<script>",page)

if __name__=="__main__":unittest.main()
