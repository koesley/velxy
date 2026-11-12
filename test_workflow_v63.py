import sqlite3
import unittest
from unittest.mock import patch
import workflow_v63 as v63
import business_agents_v59 as agents

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.access=patch.object(agents.core,"access",return_value="owner")
        self.audit=patch.object(agents.core,"audit")
        self.access.start();self.audit.start()
    def tearDown(self):
        self.access.stop();self.audit.stop();self.c.close()
    def approved_job(self,wid="a"):
        jid=agents.create_job(self.c,1,wid,"sales","Review new lead")
        agents.propose_job(self.c,1,wid,jid,"Follow up internally")
        agents.review_job(self.c,1,wid,jid,"approved","Approved")
        return jid
    def test_approved_internal_completion_and_outcome(self):
        jid=self.approved_job()
        v63.execute_internal(self.c,1,"a",jid,"Checked and completed internal task")
        with self.assertRaises(ValueError):
            v63.execute_internal(self.c,1,"a",jid,"Repeat")
        v63.record_outcome(self.c,1,"a",jid,"sale_reported","125.50","User-reported sale")
        self.assertEqual(v63.overview(self.c,1,"a")["reported_sales"],125.50)
        self.assertEqual(v63.overview(self.c,1,"b")["reported_sales"],0)
    def test_unapproved_rejected(self):
        jid=agents.create_job(self.c,1,"a","support","Handle FAQ")
        with self.assertRaises(ValueError):v63.execute_internal(self.c,1,"a",jid,"Not approved")
        with self.assertRaises(ValueError):v63.record_outcome(self.c,1,"a",jid,"other","0","Not completed")
    def test_cross_workspace_denied(self):
        jid=self.approved_job("a")
        with self.assertRaises(ValueError):v63.execute_internal(self.c,1,"b",jid,"Wrong tenant")
    def test_invalid_amount(self):
        jid=self.approved_job()
        v63.execute_internal(self.c,1,"a",jid,"Done")
        with self.assertRaises(ValueError):v63.record_outcome(self.c,1,"a",jid,"sale_reported","nan","No")
    def test_html_escaped(self):
        jid=self.approved_job()
        v63.execute_internal(self.c,1,"a",jid,"Done")
        v63.record_outcome(self.c,1,"a",jid,"other","0","<script>alert(1)</script>")
        self.assertNotIn("<script>",v63.render(self.c,1,"a","csrf"))

if __name__=="__main__":unittest.main()
