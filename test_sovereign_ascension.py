import sqlite3
import unittest
import sales_pipeline
import sovereign_ascension as asc

class AscensionTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        sales_pipeline.setup(self.c)
        asc.setup(self.c)
    def tearDown(self):
        self.c.close()
    def lead(self,owner=1,stage="proposal",days=10):
        lid=sales_pipeline.save(self.c,owner,{"business":"Example Workshop","stage":stage,"value":"200"})
        self.c.execute("UPDATE sales_pipeline_leads SET updated_at=? WHERE id=?",(1000000-days*86400,lid))
        return lid
    def test_opportunity_has_evidence_not_claimed_revenue(self):
        lid=self.lead()
        items=asc.discover(self.c,1,at=1000000)
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]["lead_id"],lid)
        self.assertIn("Unknown",items[0]["impact"])
        self.assertEqual(items[0]["contact_state"],"unverified")
    def test_owner_isolation(self):
        lid=self.lead()
        self.assertEqual(asc.discover(self.c,2,at=1000000),[])
        with self.assertRaises(ValueError):
            asc.action(self.c,2,lid,"stalled_deal","approved")
    def test_approval_completion_and_no_external_send(self):
        lid=self.lead()
        with self.assertRaises(ValueError):
            asc.action(self.c,1,lid,"stalled_deal","completed")
        asc.action(self.c,1,lid,"stalled_deal","approved")
        asc.action(self.c,1,lid,"stalled_deal","completed","Reviewed manually")
        self.assertEqual(self.c.execute("SELECT status FROM ascension_actions").fetchone()[0],"completed")
    def test_html_escape(self):
        lid=sales_pipeline.save(self.c,1,{"business":"<script>alert(1)</script>","stage":"replied"})
        self.c.execute("UPDATE sales_pipeline_leads SET updated_at=1 WHERE id=?",(lid,))
        rendered=asc.dashboard(self.c,1,"token")
        self.assertNotIn("<script>",rendered)
    def test_no_false_positive_for_recent_lead(self):
        sales_pipeline.save(self.c,1,{"business":"Recent Customer","stage":"new"})
        self.assertEqual(asc.discover(self.c,1),[])

if __name__=="__main__":
    unittest.main()
