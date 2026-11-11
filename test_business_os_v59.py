import sqlite3
import unittest
from unittest.mock import patch
import business_os_v59 as bos

class BusinessOSTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.access=patch.object(bos.core,"access",side_effect=lambda c,u,w,**kw: "owner")
        self.audit=patch.object(bos.core,"audit")
        self.access.start();self.audit.start()
    def tearDown(self):
        self.access.stop();self.audit.stop();self.c.close()
    def test_workspace_isolation_and_approval(self):
        lid=bos.add_lead(self.c,1,"alpha","Customer","customer@example.com","Referral",125)
        self.assertEqual(bos.overview(self.c,1,"alpha")["metrics"]["leads"],1)
        self.assertEqual(bos.overview(self.c,1,"beta")["metrics"]["leads"],0)
        with self.assertRaises(ValueError):
            bos.propose(self.c,1,"beta",lid,"Hello")
        aid=bos.propose(self.c,1,"alpha",lid,"Hello")
        self.assertEqual(bos.overview(self.c,1,"alpha")["metrics"]["pending_approvals"],1)
        with self.assertRaises(ValueError):
            bos.review(self.c,1,"beta",aid,"approved","Reviewed")
        bos.review(self.c,1,"alpha",aid,"approved","Reviewed")
        self.assertEqual(bos.overview(self.c,1,"alpha")["metrics"]["pending_approvals"],0)
        with self.assertRaises(ValueError):
            bos.review(self.c,1,"alpha",aid,"approved","Again")
    def test_validation_and_metrics(self):
        for amount in ("nan","inf","-1","bad"):
            with self.assertRaises(ValueError):
                bos.add_lead(self.c,1,"alpha","Name","Contact","Source",amount)
        lid=bos.add_lead(self.c,1,"alpha","Name","Contact","Source",100)
        bos.update_lead(self.c,1,"alpha",lid,"won")
        d=bos.overview(self.c,1,"alpha")
        self.assertEqual(d["metrics"]["won_reported"],100)
        self.assertEqual(d["metrics"]["open_pipeline"],0)
        self.assertIn("Name",bos.export_csv(self.c,1,"alpha"))
    def test_escaped_render(self):
        bos.add_lead(self.c,1,"alpha","<script>alert(1)</script>","contact","Source",1)
        page=bos.render(self.c,1,"alpha","csrf")
        self.assertNotIn("<script>",page)
        self.assertIn("&lt;script&gt;",page)

if __name__=="__main__":
    unittest.main()
