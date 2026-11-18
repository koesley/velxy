import sqlite3
import unittest
from unittest.mock import patch
from optimization_impact_v40 import setup,record,analyze

class ImpactTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE vx_optimization39 (id TEXT,workspace_id TEXT,revision_name TEXT,status TEXT,estimated_budget_cents INTEGER,base_campaign_id TEXT,created INTEGER)")
        self.c.execute("CREATE TABLE vx_campaign37 (id TEXT,workspace_id TEXT,name TEXT,spend_cents INTEGER,leads INTEGER,conversions INTEGER)")
        self.c.executemany("INSERT INTO vx_optimization39 VALUES (?,?,?,?,?,?,?)",[
            ("p1","one","Revised","implemented",10000,"c1",1),
            ("p2","two","Other","implemented",90000,"c2",1),
            ("p3","one","Pending","approved",1000,"c1",2)])
        self.c.executemany("INSERT INTO vx_campaign37 VALUES (?,?,?,?,?,?)",[
            ("c1","one","Original",10000,40,8),("c2","two","Other",10000,30,3)])
        setup(self.c)
    def tearDown(self):self.c.close()

    @patch("optimization_impact_v40.optimization.setup")
    @patch("optimization_impact_v40.bos.core.access")
    def test_append_only_and_scoping(self,access,init):
        with self.assertRaises(ValueError):
            record(self.c,1,"one","p2","2026-11-01","2026-11-30","100",30,5,"CRM")
        with self.assertRaises(ValueError):
            record(self.c,1,"one","p3","2026-11-01","2026-11-30","100",30,5,"CRM")
        with self.assertRaises(ValueError):
            record(self.c,1,"one","p1","2026-11-01","2026-11-30","100",2,5,"CRM")
        record(self.c,1,"one","p1","2026-11-01","2026-11-30","100",30,9,"CRM export")
        record(self.c,1,"one","p1","2026-12-01","2026-12-31","200",40,12,"Manual ledger")
        rows=analyze(self.c,1,"one")
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["percentage_point_change"],10.0)
        self.assertEqual(analyze(self.c,1,"two")[0]["snapshot_id"],None)

    @patch("optimization_impact_v40.bos.core.access",side_effect=ValueError("Denied"))
    def test_denied(self,access):
        with self.assertRaises(ValueError):analyze(self.c,1,"two")

if __name__=="__main__":unittest.main()
