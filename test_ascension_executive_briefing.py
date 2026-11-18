import sqlite3
import unittest
import time
import sales_pipeline
import sovereign_ascension as asc
import ascension_executive_briefing as briefing

class ExecutiveBriefingTests(unittest.TestCase):
    def setUp(self):self.c=sqlite3.connect(":memory:");self.now=int(time.time())
    def tearDown(self):self.c.close()
    def test_first_visit(self):
        result=briefing.briefing(self.c,1,self.now)
        self.assertEqual(result["new_leads"],0)
        self.assertEqual(result["queue"],[])
    def test_tenant_isolation(self):
        sales_pipeline.save(self.c,1,{"business":"Example","stage":"new"})
        self.assertEqual(briefing.briefing(self.c,1,self.now)["new_leads"],1)
        self.assertEqual(briefing.briefing(self.c,2,self.now)["new_leads"],0)
    def test_weekly_window(self):
        lid=sales_pipeline.save(self.c,1,{"business":"Example","stage":"new"})
        self.c.execute("UPDATE sales_pipeline_leads SET created_at=?,updated_at=? WHERE id=?",(self.now-10*86400,self.now-10*86400,lid))
        self.assertEqual(briefing.briefing(self.c,1,self.now)["new_leads"],0)
    def test_completed_action_count(self):
        lid=sales_pipeline.save(self.c,1,{"business":"Example","stage":"proposal"})
        asc.action(self.c,1,lid,"stalled_deal","approved")
        asc.action(self.c,1,lid,"stalled_deal","completed","Called")
        self.assertEqual(briefing.briefing(self.c,1,self.now)["completed"],1)
    def test_untrusted_business_not_rendered_as_html(self):
        sales_pipeline.save(self.c,1,{"business":"<script>unsafe</script>","stage":"proposal"})
        self.c.execute("UPDATE sales_pipeline_leads SET updated_at=? WHERE owner_id=1",(self.now-15*86400,))
        page=briefing.dashboard(self.c,1)
        self.assertNotIn("<script>",page)
        self.assertIn("&lt;script&gt;",page)

if __name__=="__main__":unittest.main()
