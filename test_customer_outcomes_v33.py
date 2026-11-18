import sqlite3
import unittest
from unittest.mock import patch
from customer_outcomes_v33 import add,review,snapshot,setup

class OutcomeTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE bos59_leads (id TEXT,workspace_id TEXT)")
        self.c.executemany("INSERT INTO bos59_leads VALUES (?,?)",[("a","one"),("b","two")])
        setup(self.c)
    def tearDown(self):self.c.close()

    @patch("customer_outcomes_v33.bos.init")
    @patch("customer_outcomes_v33.bos.core.access")
    def test_outcome_lifecycle(self,access,init):
        with self.assertRaises(ValueError):add(self.c,1,"one","b","payment_reported","25","Paid","receipt")
        with self.assertRaises(ValueError):add(self.c,1,"one","a","customer_retained","25","Retained","")
        with self.assertRaises(ValueError):add(self.c,1,"one","a","payment_reported","NaN","Paid","")
        identifier=add(self.c,1,"one","a","payment_reported","25.50","Customer reports payment","receipt reference")
        self.assertEqual(snapshot(self.c,1,"one")["reported_payment_cents"],2550)
        self.assertEqual(snapshot(self.c,1,"two")["records"],0)
        with self.assertRaises(ValueError):review(self.c,1,"one",identifier)
        with self.assertRaises(ValueError):review(self.c,2,"two",identifier)
        review(self.c,2,"one",identifier)
        with self.assertRaises(ValueError):review(self.c,3,"one",identifier)
        self.assertEqual(snapshot(self.c,1,"one")["internally_reviewed"],1)

    @patch("customer_outcomes_v33.bos.core.access",side_effect=ValueError("Denied"))
    def test_denied(self,access):
        with self.assertRaises(ValueError):snapshot(self.c,1,"two")

if __name__=="__main__":unittest.main()
