import sqlite3
import unittest
import sovereign_ascension as asc
import ascension_recovery as recovery

class FirstVisitTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
    def tearDown(self):
        self.c.close()
    def test_ascension_first_visit_with_empty_database(self):
        page=asc.dashboard(self.c,1,"csrf")
        self.assertIsInstance(page,str)
        self.assertEqual(asc.discover(self.c,1),[])
    def test_recovery_first_visit_with_empty_database(self):
        page=recovery.dashboard(self.c,1,"csrf")
        self.assertIn("Revenue Recovery Outcomes",page)
    def test_record_unknown_action_does_not_crash_missing_table(self):
        with self.assertRaises(ValueError):
            recovery.record(self.c,1,"unknown","responded","0","")
    def test_ascension_action_unknown_lead_is_validation_error(self):
        with self.assertRaises(ValueError):
            asc.action(self.c,1,"missing","stalled_deal","approved")

if __name__=="__main__":
    unittest.main()
