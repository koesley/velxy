import sqlite3
import unittest
import sales_pipeline
import sovereign_ascension as asc
import ascension_recovery as recovery

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        sales_pipeline.setup(self.c)
        asc.setup(self.c)
        recovery.setup(self.c)
        lid=sales_pipeline.save(self.c,1,{"business":"Test Shop","stage":"proposal"})
        self.action=asc.action(self.c,1,lid,"stalled_deal","approved")
        asc.action(self.c,1,lid,"stalled_deal","completed","Followed up manually")
    def tearDown(self):
        self.c.close()
    def test_reported_payment_is_not_verified(self):
        recovery.record(self.c,1,self.action,"payment_reported","49.00","Customer reported paid invoice")
        rendered=recovery.dashboard(self.c,1,"csrf")
        self.assertIn("user-reported payments",rendered)
        self.assertIn("NOT verified payment receipts",rendered)
    def test_other_owner_cannot_record(self):
        with self.assertRaises(ValueError):
            recovery.record(self.c,2,self.action,"responded","0","")
    def test_rejects_non_payment_amount(self):
        with self.assertRaises(ValueError):
            recovery.record(self.c,1,self.action,"responded","25","")
    def test_rejects_negative_and_precision(self):
        for value in ("-1","0.001","nan"):
            with self.assertRaises(ValueError):
                recovery.record(self.c,1,self.action,"payment_reported",value,"Valid receipt reference 123")
    def test_duplicate_outcome_rejected(self):
        recovery.record(self.c,1,self.action,"responded","0","")
        with self.assertRaises(ValueError):
            recovery.record(self.c,1,self.action,"responded","0","")

if __name__=="__main__":
    unittest.main()
