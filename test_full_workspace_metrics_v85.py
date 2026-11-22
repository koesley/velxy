"""V85: headline dashboard metrics must not truncate at 300 rows."""
import sqlite3
import unittest
from unittest.mock import patch
import business_os_v59 as bos

class FullWorkspaceMetricsTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        bos.init(self.c)
        self.access=patch.object(bos.core,"access",return_value="owner")
        self.access.start()
    def tearDown(self):
        self.access.stop()
        self.c.close()
    def add_lead(self,n,wid="a",status="new",value=10):
        self.c.execute("INSERT INTO bos59_leads(id,workspace_id,name,contact,source,value,status,created,updated) VALUES(?,?,?,?,?,?,?,?,?)",
            (str(n)+wid,wid,"Customer","email@example.com","test",value,status,n,n))
    def test_more_than_300_leads(self):
        for i in range(350):self.add_lead(i)
        result=bos.overview(self.c,1,"a")
        self.assertEqual(len(result["leads"]),300)
        self.assertEqual(result["metrics"]["leads"],350)
        self.assertEqual(result["metrics"]["open_pipeline"],3500)
    def test_tenant_isolation(self):
        self.add_lead(1,"a")
        self.add_lead(2,"b",value=900)
        result=bos.overview(self.c,1,"a")
        self.assertEqual(result["metrics"]["leads"],1)
        self.assertEqual(result["metrics"]["open_pipeline"],10)
    def test_won_excluded_from_open(self):
        self.add_lead(1,status="won",value=99)
        result=bos.overview(self.c,1,"a")
        self.assertEqual(result["metrics"]["won_reported"],99)
        self.assertEqual(result["metrics"]["open_pipeline"],0)
    def test_pending_approvals_beyond_preview(self):
        for i in range(305):
            self.c.execute("INSERT INTO bos59_actions(id,workspace_id,lead_id,message,decision,reason,created_by,created) VALUES(?,?,?,?,?,?,?,?)",
                (str(i),"a","lead","draft","pending","",1,i))
        result=bos.overview(self.c,1,"a")
        self.assertEqual(len(result["actions"]),300)
        self.assertEqual(result["metrics"]["pending_approvals"],305)
    def test_empty_workspace(self):
        self.assertEqual(bos.overview(self.c,1,"a")["metrics"],
            {"leads":0,"open_pipeline":0,"won_reported":0,"pending_approvals":0})

if __name__=="__main__":unittest.main()
