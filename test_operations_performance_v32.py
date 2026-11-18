import sqlite3
import unittest
from unittest.mock import patch
from operations_performance_v32 import analyze

class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("""CREATE TABLE vx_recovery31 (
            workspace_id TEXT,task_id TEXT,diagnosis TEXT,status TEXT,
            created INTEGER,updated INTEGER,due_date TEXT)""")
        self.c.executemany("INSERT INTO vx_recovery31 VALUES (?,?,?,?,?,?,?)",[
            ("one","t1","blocked","resolved",100,864100,"2026-01-01"),
            ("one","t1","blocked again","open",100,200,"2000-01-01"),
            ("one","t2","other","open",100,200,"2099-01-01"),
            ("two","t3","private","resolved",100,200,"2026-01-01")])
    def tearDown(self):self.c.close()

    @patch("operations_performance_v32.recovery.setup")
    @patch("operations_performance_v32.bos.core.access")
    def test_workspace_metrics(self,access,setup):
        data=analyze(self.c,1,"one")
        self.assertEqual(data["total"],3)
        self.assertEqual(data["resolved"],1)
        self.assertEqual(data["recurring_tasks"],1)
        self.assertEqual(data["overdue_open"],1)
        self.assertEqual(data["average_resolution_days"],10.0)
        access.assert_called_once_with(self.c,1,"one")

    @patch("operations_performance_v32.bos.core.access",side_effect=ValueError("Denied"))
    def test_denied(self,access):
        with self.assertRaises(ValueError):analyze(self.c,1,"two")

if __name__=="__main__":unittest.main()
