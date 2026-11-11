"""V59 suite tests using isolated SQLite fixtures; PostgreSQL integration requires staging."""
import sqlite3
import unittest
import ascension_suite_v59 as v59

DDL = [
"CREATE TABLE empire_members(workspace_id TEXT,user_id TEXT)",
"CREATE TABLE v59_contacts(id TEXT PRIMARY KEY,workspace TEXT,name TEXT,email TEXT,created INTEGER)",
"CREATE TABLE v59_deals(id TEXT PRIMARY KEY,workspace TEXT,contact TEXT,title TEXT,cents INTEGER,stage TEXT,created INTEGER)",
"CREATE TABLE v59_audits(id TEXT PRIMARY KEY,workspace TEXT,url TEXT,findings TEXT,created INTEGER)",
"CREATE TABLE v59_workflows(id TEXT PRIMARY KEY,workspace TEXT,name TEXT,trigger_kind TEXT,action_kind TEXT,enabled INTEGER)",
"CREATE TABLE v59_runs(id TEXT PRIMARY KEY,workspace TEXT,workflow TEXT,status TEXT,details TEXT,created INTEGER)",
"CREATE TABLE v59_agents(workspace TEXT,kind TEXT,installed INTEGER,PRIMARY KEY(workspace,kind))",
"CREATE TABLE v59_agent_runs(id TEXT PRIMARY KEY,workspace TEXT,kind TEXT,report TEXT,created INTEGER)",
]
class SuiteTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        for sql in DDL:self.c.execute(sql)
        self.c.execute("INSERT INTO empire_members VALUES ('a','alice')")
        self.c.execute("INSERT INTO empire_members VALUES ('b','bob')")
    def tearDown(self):self.c.close()
    def test_tenant_isolation(self):
        with self.assertRaises(ValueError):v59.act(self.c,"bob","a",{"action":"contact","name":"X"})
        v59.act(self.c,"alice","a",{"action":"contact","name":"Alice"})
        with self.assertRaises(ValueError):v59.render(self.c,"bob","a","token")
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM v59_contacts WHERE workspace='a'").fetchone()[0],1)
    def test_contact_and_deal(self):
        v59.act(self.c,"alice","a",{"action":"contact","name":"Customer","email":"customer@example.com"})
        contact=self.c.execute("SELECT id FROM v59_contacts").fetchone()[0]
        v59.act(self.c,"alice","a",{"action":"deal","contact":contact,"title":"Service","cents":"12500"})
        deal=self.c.execute("SELECT id FROM v59_deals").fetchone()[0]
        v59.act(self.c,"alice","a",{"action":"stage","id":deal,"stage":"won"})
        self.assertIn("$125.00",v59.render(self.c,"alice","a","csrf"))
    def test_html_audit(self):
        self.assertIn("Missing document title",v59.analyze("<html><body><img src='x'></body></html>")["findings"])
    def test_workflow_and_agent(self):
        v59.act(self.c,"alice","a",{"action":"workflow","name":"CRM summary"})
        wid=self.c.execute("SELECT id FROM v59_workflows").fetchone()[0]
        v59.act(self.c,"alice","a",{"action":"workflow_toggle","id":wid})
        v59.act(self.c,"alice","a",{"action":"workflow_run","id":wid})
        v59.act(self.c,"alice","a",{"action":"agent_install","agent":"sales"})
        v59.act(self.c,"alice","a",{"action":"agent_run","agent":"sales"})
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM v59_runs").fetchone()[0],1)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM v59_agent_runs").fetchone()[0],1)
if __name__=="__main__":unittest.main()
