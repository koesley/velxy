import sqlite3
import unittest
from datetime import datetime
from unittest.mock import patch
from revenue_recovery_v31 import create,resolve,candidates,setup

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE bos59_leads (workspace_id TEXT,id TEXT,name TEXT)")
        self.c.execute("""CREATE TABLE vx_revenue_tasks29
            (id TEXT,workspace_id TEXT,lead_id TEXT,title TEXT,status TEXT,due_date TEXT,
            updated INTEGER,owner_id INTEGER,created INTEGER)""")
        self.c.executemany("INSERT INTO bos59_leads VALUES (?,?,?)",[("one","l","Lead"),("two","x","Other")])
        self.c.executemany("INSERT INTO vx_revenue_tasks29 VALUES (?,?,?,?,?,?,?,?,?)",[
            ("t","one","l","Call","blocked","2026-01-01",1,7,1),
            ("other","two","x","Other task","blocked","2026-01-01",1,8,1)])
        setup(self.c)
    def tearDown(self):self.c.close()

    @patch("revenue_recovery_v31.bos.core.access")
    def test_owner_and_scope(self,access):
        self.assertEqual(len(candidates(self.c,7,"one",now=int(datetime(2026,11,18).timestamp()))),1)
        with self.assertRaises(ValueError):create(self.c,7,"one","other","blocked","call")
        with self.assertRaises(ValueError):create(self.c,8,"one","t","blocked","call")
        identifier=create(self.c,7,"one","t","Waiting on data","Request details")
        with self.assertRaises(ValueError):create(self.c,7,"one","t","Waiting","Request")
        with self.assertRaises(ValueError):resolve(self.c,8,"one",identifier)
        resolve(self.c,7,"one",identifier)
        with self.assertRaises(ValueError):resolve(self.c,7,"one",identifier)

    @patch("revenue_recovery_v31.bos.core.access",side_effect=ValueError("Denied"))
    def test_denied(self,access):
        with self.assertRaises(ValueError):candidates(self.c,7,"one")

if __name__=="__main__":unittest.main()
