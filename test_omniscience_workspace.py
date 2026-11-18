import sqlite3
import unittest
import omniscience_workspace as workspace
import omniscience_evidence as ledger

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
    def tearDown(self):
        self.c.close()
    def test_first_visit(self):
        page=workspace.dashboard(self.c,1)
        self.assertIn("No recorded recommendations",page)
        self.assertIn("No actionable aging CRM",page)
    def test_cross_tenant_and_escaping(self):
        evidence=ledger.record_evidence(self.c,1,"manual","1","user_reported",{"value":"<img>"})
        rec=ledger.recommend(self.c,1,"<script>alert(1)</script>","check","review",evidence)
        ledger.decide(self.c,1,rec,"defer","<img src=x onerror=alert(1)>")
        own=workspace.dashboard(self.c,1)
        other=workspace.dashboard(self.c,2)
        self.assertIn("&lt;script&gt;",own)
        self.assertIn("&lt;img src=x",own)
        self.assertNotIn("<script>",own)
        self.assertNotIn("<img src=x",own)
        self.assertNotIn("alert(1)",other)
        self.assertNotIn("manual / 1",other)
    def test_requires_account(self):
        for owner in (0,-1,True,"1"):
            with self.assertRaises(ValueError):
                workspace.dashboard(self.c,owner)

if __name__=="__main__":
    unittest.main()
