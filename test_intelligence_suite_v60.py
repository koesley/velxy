"""Isolated V60 tests; production PostgreSQL must be validated in staging."""
import sqlite3
import unittest
import intelligence_suite_v60 as v60
class V60Tests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        for sql in (
          "CREATE TABLE empire_members(workspace_id TEXT,user_id TEXT)",
          "CREATE TABLE v59_contacts(id TEXT,workspace TEXT,name TEXT,email TEXT,created INTEGER)",
          "CREATE TABLE v59_deals(id TEXT,workspace TEXT,contact TEXT,title TEXT,cents INTEGER,stage TEXT,created INTEGER)",
          "CREATE TABLE v59_audits(id TEXT,workspace TEXT,url TEXT,findings TEXT,created INTEGER)",
          "CREATE TABLE v60_records(id TEXT PRIMARY KEY,workspace TEXT,kind TEXT,title TEXT,payload TEXT,created INTEGER)",
        ):self.c.execute(sql)
        self.c.execute("INSERT INTO empire_members VALUES ('a','alice')")
        self.c.execute("INSERT INTO empire_members VALUES ('b','bob')")
    def tearDown(self):self.c.close()
    def test_all_six_tools_persist(self):
        actions=[
          {"kind":"opportunity"},
          {"kind":"knowledge","title":"Policy","body":"Follow up on new leads."},
          {"kind":"scenario","base":"100","change":"10"},
          {"kind":"command","question":"pipeline"},
          {"kind":"portal","title":"Customer hub","body":"Welcome"},
          {"kind":"decision","option_a":"A","option_b":"B","score_a":"8","score_b":"4"},
        ]
        for f in actions:v60.act(self.c,"alice","a",f)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM v60_records WHERE workspace='a'").fetchone()[0],6)
        page=v60.render(self.c,"alice","a","token")
        for label in v60.LABELS.values():self.assertIn(label,page)
        self.assertIn("Projected value: $110.00",page)
    def test_knowledge_search_and_private_preview(self):
        v60.act(self.c,"alice","a",{"kind":"knowledge","title":"Retention","body":"Follow up with inactive customers"})
        self.assertIn("Retention",v60.command(self.c,"a","search knowledge inactive"))
        self.assertEqual(v60.search_knowledge(self.c,"b","inactive"),[])
        v60.act(self.c,"alice","a",{"kind":"portal","title":"Client Center","body":"Welcome customers"})
        record=self.c.execute("SELECT id FROM v60_records WHERE kind='portal'").fetchone()[0]
        self.assertIn("Client Center",v60.portal_preview(self.c,"alice","a",record))
        with self.assertRaises(ValueError):v60.portal_preview(self.c,"bob","a",record)
    def test_sales_funnel(self):
        self.c.execute("INSERT INTO v59_deals VALUES ('1','a','x','Project',2500,'lead',1)")
        self.assertIn("lead: 1 deals",v60.command(self.c,"a","sales funnel"))
        self.assertEqual(v60.sales_funnel(self.c,"b"),{})
    def test_tenant_isolation(self):
        with self.assertRaises(ValueError):v60.act(self.c,"bob","a",{"kind":"opportunity"})
        with self.assertRaises(ValueError):v60.render(self.c,"bob","a","token")
    def test_invalid_values(self):
        for f in ({"kind":"scenario","base":"nan","change":"10"},{"kind":"decision","option_a":"A","option_b":"B","score_a":"11","score_b":"1"}):
            with self.assertRaises(ValueError):v60.act(self.c,"alice","a",f)
    def test_safe_command(self):
        self.assertEqual(v60.command(self.c,"a","delete all contacts"),"Unsupported request. Try: contacts, pipeline, revenue, opportunities, sales funnel, search knowledge TERM.")
if __name__=="__main__":unittest.main()
