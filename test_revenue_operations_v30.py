import sqlite3
import unittest
from datetime import datetime
from unittest.mock import patch
from revenue_operations_v30 import analyze,render

class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("""CREATE TABLE vx_revenue_tasks29
            (workspace_id TEXT,status TEXT,due_date TEXT,updated INTEGER,created INTEGER,owner_id INTEGER)""")
        self.now=int(datetime(2026,11,18,12,0).timestamp())
        self.c.executemany("INSERT INTO vx_revenue_tasks29 VALUES (?,?,?,?,?,?)",[
            ("one","todo","2026-11-01",self.now-9*86400,self.now-10*86400,7),
            ("one","blocked","2026-11-25",self.now-86400,self.now-2*86400,8),
            ("one","done","2026-11-01",self.now-86400,self.now-4*86400,7),
            ("two","todo","2026-11-01",self.now-9*86400,self.now-10*86400,9)])
    def tearDown(self):self.c.close()

    @patch("revenue_operations_v30.execution.setup")
    @patch("revenue_operations_v30.bos.core.access")
    def test_scoped_metrics(self,access,setup):
        result=analyze(self.c,1,"one",now=self.now)
        self.assertEqual(result["total"],3)
        self.assertEqual(result["overdue"],1)
        self.assertEqual(result["stalled"],1)
        self.assertEqual(result["blocked"],1)
        self.assertEqual(result["completed"],1)
        self.assertEqual(result["owner_count"],2)
        self.assertEqual(result["completion_pct"],33.3)
        access.assert_called_once_with(self.c,1,"one")

    @patch("revenue_operations_v30.bos.core.access",side_effect=ValueError("Denied"))
    def test_access_denied(self,access):
        with self.assertRaises(ValueError):analyze(self.c,1,"two",now=self.now)

if __name__=="__main__":unittest.main()
