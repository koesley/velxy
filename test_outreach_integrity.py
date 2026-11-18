"""Regression tests for irreversible outreach safety decisions."""
import sqlite3
import unittest
import sales_pipeline

class OutreachIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        sales_pipeline.setup(self.db)
    def tearDown(self):
        self.db.close()
    def test_permanent_bounce_cannot_be_cleared(self):
        sales_pipeline.set_suppression(self.db,1,"bad@example.com","suppress_permanent","550 mailbox unknown")
        with self.assertRaises(ValueError):
            sales_pipeline.set_suppression(self.db,1,"bad@example.com","verified_clear","Public business email confirmed today")
        self.assertFalse(sales_pipeline.outreach_eligibility(self.db,1,"bad@example.com"))
    def test_rejected_cannot_be_downgraded(self):
        sales_pipeline.set_suppression(self.db,1,"bad@example.com","suppress_rejected","blocked")
        with self.assertRaises(ValueError):
            sales_pipeline.set_suppression(self.db,1,"bad@example.com","hold_for_verification","retry")
    def test_owner_isolation(self):
        sales_pipeline.set_suppression(self.db,1,"bad@example.com","do_not_contact")
        sales_pipeline.set_suppression(self.db,2,"bad@example.com","verified_clear","Public website contact listing")
        self.assertFalse(sales_pipeline.outreach_eligibility(self.db,1,"bad@example.com"))
        self.assertTrue(sales_pipeline.outreach_eligibility(self.db,2,"bad@example.com"))
    def test_overlong_evidence_does_not_write(self):
        with self.assertRaises(ValueError):
            sales_pipeline.set_suppression(self.db,1,"bad@example.com","hold_for_verification","x"*501)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM outreach_suppression_events").fetchone()[0],0)
    def test_malformed_lead_email_rejected(self):
        with self.assertRaises(ValueError):
            sales_pipeline.save(self.db,1,{"business":"Example Shop","email":"a@invalid"})
    def test_import_never_downgrades_optout(self):
        sales_pipeline.set_suppression(self.db,1,"stop@example.com","do_not_contact")
        sales_pipeline.import_bounce_lines(self.db,1,"stop@example.com | timed out")
        self.assertFalse(sales_pipeline.outreach_eligibility(self.db,1,"stop@example.com"))
    def test_ui_explains_irreversible_suppression(self):
        self.assertIn("Permanent suppressions and opt-outs cannot be cleared",sales_pipeline.dashboard(self.db,1,"csrf"))
if __name__=="__main__":
    unittest.main()
