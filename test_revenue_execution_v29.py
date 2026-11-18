import sqlite3
import unittest
from unittest.mock import patch
from revenue_execution_v29 import create,change,setup

class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE bos59_leads (workspace_id TEXT,id TEXT,status TEXT)")
        self.c.executemany("INSERT INTO bos59_leads VALUES (?,?,?)",[("a","lead1","new"),("b","lead2","new"),("a","closed","won")])
        setup(self.c)
    def tearDown(self):self.c.close()

    @patch("revenue_execution_v29.bos.init")
    @patch("revenue_execution_v29.bos.core.access")
    def test_task_lifecycle(self,access,init):
        with self.assertRaises(ValueError):create(self.c,7,"a","lead2","Call","2026-12-01")
        with self.assertRaises(ValueError):create(self.c,7,"a","closed","Call","2026-12-01")
        identifier=create(self.c,7,"a","lead1","Call","2026-12-01")
        with self.assertRaises(ValueError):create(self.c,7,"a","lead1","Call","2026-12-01")
        with self.assertRaises(ValueError):change(self.c,8,"a",identifier,"done")
        with self.assertRaises(ValueError):change(self.c,7,"b",identifier,"done")
        change(self.c,7,"a",identifier,"in_progress")
        change(self.c,7,"a",identifier,"done")
        with self.assertRaises(ValueError):change(self.c,7,"a",identifier,"todo")

    @patch("revenue_execution_v29.bos.core.access",side_effect=ValueError("Denied"))
    def test_permission_failure(self,access):
        with self.assertRaises(ValueError):change(self.c,7,"a","fake","done")

if __name__=="__main__":unittest.main()
