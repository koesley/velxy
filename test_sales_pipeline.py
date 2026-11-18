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
        sales_pipeline.set_suppression(self.c,1,"info@example.com","verified_clear","Current public company website contact page")
        sales_pipeline.set_suppression(self.c,1,"info@example.com","do_not_contact")
        self.assertFalse(sales_pipeline.outreach_eligibility(self.c,1,"info@example.com"))
    def test_bulk_bounce_import(self):
        count=sales_pipeline.import_bounce_lines(self.c,1,
            "bad@example.com | 550 5.1.1 User does not exist\\nslow@example.com | timed out")
        self.assertEqual(count,2)
        statuses=dict(self.c.execute("SELECT email,status FROM outreach_suppression WHERE owner_id=1").fetchall())
        self.assertEqual(statuses["bad@example.com"],"suppress_permanent")
        self.assertEqual(statuses["slow@example.com"],"hold_for_verification")

    def test_import_preserves_opt_out(self):
        sales_pipeline.set_suppression(self.c,1,"stop@example.com","do_not_contact")
        sales_pipeline.import_bounce_lines(self.c,1,"stop@example.com | timed out")
        self.assertFalse(sales_pipeline.outreach_eligibility(self.c,1,"stop@example.com"))
        status=self.c.execute("SELECT status FROM outreach_suppression WHERE email='stop@example.com'").fetchone()[0]
        self.assertEqual(status,"do_not_contact")

    def test_import_rejects_bad_lines(self):
        with self.assertRaises(ValueError):
            sales_pipeline.import_bounce_lines(self.c,1,"bad format")

    def test_gmail_notice_import(self):
        notice="Delivery incomplete\\nThere was a temporary problem delivering your message to hello@example.com.\\nThe response was: timed out"
        count=sales_pipeline.import_gmail_notices(self.c,1,notice)
        self.assertEqual(count,1)
        status=self.c.execute("SELECT status FROM outreach_suppression WHERE owner_id=1 AND email='hello@example.com'").fetchone()[0]
        self.assertEqual(status,"hold_for_verification")

    def test_gmail_notice_invalid(self):
        with self.assertRaises(ValueError):
            sales_pipeline.import_gmail_notices(self.c,1,"Some unrelated message")

    def test_opt_out_cannot_be_reactivated(self):
        sales_pipeline.set_suppression(self.c,1,"stop@example.com","do_not_contact")
        with self.assertRaises(ValueError):
            sales_pipeline.set_suppression(self.c,1,"stop@example.com","verified_clear","Website contact page verified")

    def test_verified_requires_evidence(self):
        with self.assertRaises(ValueError):
            sales_pipeline.set_suppression(self.c,1,"hello@example.com","verified_clear","")

    def test_audit_events(self):
        sales_pipeline.set_suppression(self.c,1,"hello@example.com","hold_for_verification","timeout")
        sales_pipeline.set_suppression(self.c,1,"hello@example.com","suppress_permanent","550 5.1.1")
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM outreach_suppression_events WHERE owner_id=1").fetchone()[0],2)

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
