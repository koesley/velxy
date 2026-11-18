import sqlite3
import time
import unittest
import sales_pipeline
import sovereign_ascension as asc
import ascension_next_actions as engine

class NextActionsTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.now=int(time.time())
    def tearDown(self):self.c.close()
    def lead(self,owner=1,stage="proposal",days=10,business="Example Cafe"):
        lid=sales_pipeline.save(self.c,owner,{"business":business,"email":"hello@example.com","stage":stage,"value":"1200"})
        self.c.execute("UPDATE sales_pipeline_leads SET updated_at=? WHERE id=?",(self.now-days*86400,lid))
        return lid
    def test_first_visit_empty(self):
        self.assertEqual(engine.recommendations(self.c,1,now=self.now),[])
    def test_stale_proposal_is_prioritized(self):
        self.lead()
        items=engine.recommendations(self.c,1,now=self.now)
        self.assertEqual(items[0]["state"],"needs_review")
        self.assertEqual(items[0]["estimated_value"],1200)
    def test_recent_lead_not_included(self):
        self.lead(days=1)
        self.assertEqual(engine.recommendations(self.c,1,now=self.now),[])
    def test_owner_isolation(self):
        self.lead(owner=1)
        self.assertEqual(engine.recommendations(self.c,2,now=self.now),[])
    def test_dismissed_is_excluded(self):
        lid=self.lead()
        asc.action(self.c,1,lid,"stalled_deal","dismissed")
        self.assertEqual(engine.recommendations(self.c,1,now=self.now),[])
    def test_approved_contact_not_verified_is_blocked(self):
        lid=self.lead()
        asc.action(self.c,1,lid,"stalled_deal","approved")
        self.assertEqual(engine.recommendations(self.c,1,now=self.now)[0]["state"],"contact_blocked")
    def test_completed_action_needs_outcome(self):
        lid=self.lead()
        asc.action(self.c,1,lid,"stalled_deal","approved")
        asc.action(self.c,1,lid,"stalled_deal","completed","Manual call")
        self.assertEqual(engine.recommendations(self.c,1,now=self.now)[0]["state"],"awaiting_outcome")
    def test_html_escaping(self):
        self.lead(business="<script>evil</script>")
        page=engine.dashboard(self.c,1)
        self.assertNotIn("<script>",page)
        self.assertIn("&lt;script&gt;",page)

if __name__=="__main__":unittest.main()
