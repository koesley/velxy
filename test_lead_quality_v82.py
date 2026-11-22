import sqlite3
import unittest
from lead_quality_v82 import inspect_leads

class LeadQualityTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE bos59_leads(id TEXT,name TEXT,contact TEXT,status TEXT,workspace_id TEXT,created INTEGER)")
    def add(self, id, name, email, status="new", workspace="a"):
        self.c.execute("INSERT INTO bos59_leads VALUES(?,?,?,?,?,?)",(id,name,email,status,workspace,1))
    def tearDown(self): self.c.close()
    def test_clean(self):
        self.add("1","Jane","jane@example.com")
        self.assertEqual(inspect_leads(self.c,"a")["flagged"],0)
    def test_duplicates_case_insensitive(self):
        self.add("1","Jane","Jane@Example.com")
        self.add("2","Jane"," jane@example.com ")
        self.assertEqual(inspect_leads(self.c,"a")["flagged"],1)
    def test_invalid_contact(self):
        self.add("1","Jane","not-an-email")
        self.assertIn("invalid_contact_email",inspect_leads(self.c,"a")["issues"][0]["flags"])
    def test_missing_name(self):
        self.add("1"," ","jane@example.com")
        self.assertIn("missing_name",inspect_leads(self.c,"a")["issues"][0]["flags"])
    def test_cross_tenant_isolation(self):
        self.add("1","Jane","jane@example.com",workspace="b")
        self.assertEqual(inspect_leads(self.c,"a")["inspected"],0)
    def test_read_only(self):
        self.add("1","Jane","bad")
        inspect_leads(self.c,"a")
        self.assertEqual(self.c.execute("SELECT contact FROM bos59_leads").fetchone()[0],"bad")
    def test_truncated(self):
        self.add("1","Jane","jane@example.com")
        self.add("2","Sam","sam@example.com")
        self.assertTrue(inspect_leads(self.c,"a",1)["sample_truncated"])
    def test_limit_validation(self):
        with self.assertRaises(ValueError):inspect_leads(self.c,"a",True)
if __name__=="__main__":unittest.main()
