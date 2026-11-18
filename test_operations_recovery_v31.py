import sqlite3
import unittest
from unittest.mock import patch
from operations_recovery_v31 import create,resolve,setup

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("""CREATE TABLE vx_revenue_tasks29
            (id TEXT,workspace_id TEXT,owner_id INTEGER,status TEXT)""")
        self.c.executemany("INSERT INTO vx_revenue_tasks29 VALUES (?,?,?,?)",[
            ("task1","one",7,"blocked"),("task2","two",7,"blocked"),
            ("task3","one",8,"blocked"),("task4","one",7,"done")])
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
