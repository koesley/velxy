import sqlite3
import time
import unittest
import sales_pipeline
import sovereign_ascension as asc
import ascension_workflows as wf
import sovereign_intelligence_core as core

class SovereignCoreTests(unittest.TestCase):
    def setUp(self):self.c=sqlite3.connect(":memory:");self.now=int(time.time())
    def tearDown(self):self.c.close()
    def test_first_visit(self):
        ctx=core.context(self.c,1,self.now)
        self.assertEqual(ctx["leads"],[])
        self.assertEqual(ctx["recommendations"],[])
    def test_isolation(self):
        sales_pipeline.save(self.c,1,{"business":"Example Cafe","stage":"new"})
        self.assertEqual(len(core.context(self.c,1,self.now)["leads"]),1)
        self.assertEqual(core.context(self.c,2,self.now)["leads"],[])
    def test_provenance(self):
        lid=sales_pipeline.save(self.c,1,{"business":"Example Cafe","stage":"proposal","value":"2500"})
        aid=asc.action(self.c,1,lid,"stalled_deal","approved")
        wf.create(self.c,1,aid)
        lead=core.context(self.c,1,self.now)["leads"][0]
        self.assertEqual(lead["source"],"sales_pipeline_leads")
        self.assertEqual(lead["reliability"],"user_entered")
        self.assertEqual(lead["workflows"][0]["reliability"],"system_recorded")
        self.assertEqual(lead["estimated_value"],2500)
    def test_cross_owner_links_excluded(self):
        lid=sales_pipeline.save(self.c,1,{"business":"Example Cafe","stage":"proposal"})
        aid=asc.action(self.c,1,lid,"stalled_deal","approved")
        self.assertEqual(core.context(self.c,2,self.now)["leads"],[])
        self.assertEqual(core.context(self.c,1,self.now)["leads"][0]["actions"][0]["id"],aid)
    def test_recommendation_is_not_revenue_prediction(self):
        lid=sales_pipeline.save(self.c,1,{"business":"Example Cafe","stage":"proposal","value":"2000"})
        self.c.execute("UPDATE sales_pipeline_leads SET updated_at=? WHERE id=?",(self.now-15*86400,lid))
        item=core.decisions(self.c,1,self.now)[0]
        self.assertIn("not collected revenue",item["financial_impact"])
        self.assertIn("not a calibrated",item["uncertainty"])
    def test_html_escaping(self):
        lid=sales_pipeline.save(self.c,1,{"business":"<script>alert(1)</script>","stage":"proposal"})
        self.c.execute("UPDATE sales_pipeline_leads SET updated_at=? WHERE id=?",(self.now-15*86400,lid))
        page=core.dashboard(self.c,1)
        self.assertNotIn("<script>",page)
        self.assertIn("&lt;script&gt;",page)
if __name__=="__main__":unittest.main()
