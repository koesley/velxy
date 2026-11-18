import sqlite3
import unittest
from unittest.mock import patch
from operations_recovery_v31 import create,resolve,setup

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("""CREATE TABLE vx_revenue_tasks29
            (id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,lead_id TEXT NOT NULL,
            title TEXT NOT NULL,owner_id INTEGER NOT NULL,due_date TEXT NOT NULL,
            status TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL)""")
        self.c.executemany("INSERT INTO vx_revenue_tasks29 VALUES (?,?,?,?,?,?,?,?,?)",[
            ("task1","one","lead1","Task one",7,"2026-12-01","blocked",0,0),
            ("task2","two","lead2","Task two",7,"2026-12-01","blocked",0,0),
            ("task3","one","lead3","Task three",8,"2026-12-01","blocked",0,0),
            ("task4","one","lead4","Task four",7,"2026-12-01","done",0,0)])
        setup(self.c)
    def tearDown(self):self.c.close()

    @patch("operations_recovery_v31.execution.setup")
    @patch("operations_recovery_v31.bos.core.access")
    def test_recovery_lifecycle(self,access,setup_task):
        with self.assertRaises(ValueError):
            create(self.c,7,"one","task2","Blocked","Contact owner","2026-12-01")
        with self.assertRaises(ValueError):
            create(self.c,7,"one","task3","Blocked","Contact owner","2026-12-01")
        with self.assertRaises(ValueError):
            create(self.c,7,"one","task4","Blocked","Contact owner","2026-12-01")
        identifier=create(self.c,7,"one","task1","Blocked","Contact owner","2026-12-01")
        with self.assertRaises(ValueError):
            create(self.c,7,"one","task1","Blocked","Contact owner","2026-12-01")
        with self.assertRaises(ValueError):resolve(self.c,8,"one",identifier)
        with self.assertRaises(ValueError):resolve(self.c,7,"two",identifier)
        resolve(self.c,7,"one",identifier)
        with self.assertRaises(ValueError):resolve(self.c,7,"one",identifier)

    @patch("operations_recovery_v31.bos.core.access",side_effect=ValueError("Denied"))
    def test_authorization(self,access):
        with self.assertRaises(ValueError):resolve(self.c,7,"one","fake")

if __name__=="__main__":unittest.main()
