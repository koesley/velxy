import sqlite3
import unittest
import sales_pipeline

class SalesPipelineTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        sales_pipeline.setup(self.c)
    def tearDown(self):
        self.c.close()
    def test_owner_isolation(self):
        lid=sales_pipeline.save(self.c,1,{"business":"Example Cafe","stage":"new","value":"49"})
        html=sales_pipeline.dashboard(self.c,2,"csrf")
        self.assertNotIn("Example Cafe",html)
        with self.assertRaises(ValueError):
            sales_pipeline.save(self.c,2,{"lead_id":lid,"business":"Changed","stage":"won"})
    def test_stage_update(self):
        lid=sales_pipeline.save(self.c,1,{"business":"Example Cafe","stage":"new"})
        sales_pipeline.save(self.c,1,{"lead_id":lid,"business":"Example Cafe","stage":"won","value":"49"})
        self.assertIn("Self-reported won deals: $49",sales_pipeline.dashboard(self.c,1,"csrf"))
    def test_unverified_settlement_not_counted(self):
        self.c.execute("CREATE TABLE btcpay_orders(order_id TEXT,user_id INTEGER,network TEXT,status TEXT,settled_at INTEGER,invoice_id TEXT)")
        self.c.execute("CREATE TABLE subscriptions(user_id INTEGER,verification_source TEXT,verified_at INTEGER,source_reference TEXT)")
        self.c.execute("INSERT INTO btcpay_orders VALUES ('order-1',1,'mainnet','settled',100,'invoice-1')")
        self.c.execute("INSERT INTO subscriptions VALUES (1,'manual',100,'invoice-1')")
        self.assertIn('Currently evidenced mainnet PRO payments: 0',sales_pipeline.dashboard(self.c,1,'csrf'))

    def test_current_verified_invoice_counted_once(self):
        self.c.execute("CREATE TABLE btcpay_orders(order_id TEXT,user_id INTEGER,network TEXT,status TEXT,settled_at INTEGER,invoice_id TEXT)")
        self.c.execute("CREATE TABLE subscriptions(user_id INTEGER,verification_source TEXT,verified_at INTEGER,source_reference TEXT)")
        self.c.execute("INSERT INTO btcpay_orders VALUES ('order-1',1,'mainnet','settled',100,'invoice-1')")
        self.c.execute("INSERT INTO subscriptions VALUES (1,'btcpay_mainnet_verified',100,'invoice-1')")
        self.assertIn('Currently evidenced mainnet PRO payments: 1',sales_pipeline.dashboard(self.c,1,'csrf'))

    def test_outreach_default_hold(self):
        self.assertFalse(sales_pipeline.outreach_eligibility(self.c,1,"info@example.com"))
    def test_owner_scoped_suppression(self):
        sales_pipeline.set_suppression(self.c,1,"info@example.com","verified_clear","Public business contact confirmed")
        self.assertTrue(sales_pipeline.outreach_eligibility(self.c,1,"info@example.com"))
        self.assertFalse(sales_pipeline.outreach_eligibility(self.c,2,"info@example.com"))
    def test_opt_out_blocks(self):
        sales_pipeline.set_suppression(self.c,1,"info@example.com","verified_clear")
        sales_pipeline.set_suppression(self.c,1,"info@example.com","do_not_contact")
        self.assertFalse(sales_pipeline.outreach_eligibility(self.c,1,"info@example.com"))
    def test_bad_stage(self):
        with self.assertRaises(ValueError):
            sales_pipeline.save(self.c,1,{"business":"Example Cafe","stage":"invented"})
    def test_escaping(self):
        sales_pipeline.save(self.c,1,{"business":"<script>alert(1)</script>","stage":"new"})
        html=sales_pipeline.dashboard(self.c,1,"csrf")
        self.assertNotIn("<script>",html)
        self.assertIn("&lt;script&gt;",html)

if __name__=="__main__":
    unittest.main()
