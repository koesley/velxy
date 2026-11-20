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
    def test_newer_high_priority_not_hidden_by_500_old_leads(self):
        for i in range(505):
            self.lead(stage="new",days=40,business="Old %04d" % i)
        lid=self.lead(stage="replied",days=3,business="Urgent Reply")
        items=engine.recommendations(self.c,1,now=self.now)
        self.assertEqual(len(items),100)
        self.assertIn(lid,[item["lead_id"] for item in items])
        self.assertEqual(items[0]["business"],"Urgent Reply")
    def test_exact_age_boundaries_and_unrelated_stages(self):
        self.lead(stage="proposal",days=6,business="Too soon")
        self.lead(stage="replied",days=2,business="Reply")
        self.lead(stage="new",days=7,business="Aging")
        self.lead(stage="won",days=90,business="Closed")
        names={item["business"] for item in engine.recommendations(self.c,1,now=self.now)}
        self.assertEqual(names,{"Reply","Aging"})
    def test_deterministic_tie_break_for_same_business(self):
        a=self.lead(stage="proposal",days=10,business="Same")
        b=self.lead(stage="proposal",days=10,business="Same")
        ids=[x["lead_id"] for x in engine.recommendations(self.c,1,now=self.now)]
        self.assertEqual(ids,[a,b])
    def test_queue_discloses_preview_limit(self):
        self.lead()
        self.assertIn("up to 100 highest-priority",engine.dashboard(self.c,1))
    def test_html_escaping(self):
        self.lead(business="<script>evil</script>")
        page=engine.dashboard(self.c,1)
        self.assertNotIn("<script>",page)
        self.assertIn("&lt;script&gt;",page)

if __name__=="__main__":unittest.main()
