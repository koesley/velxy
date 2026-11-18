"""Regression checks for owner isolation and stale workflow transitions."""
import sqlite3
import time
import unittest
import sales_pipeline
import sovereign_ascension
import ascension_workflows

class WorkflowHardeningTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.lead=sales_pipeline.save(self.c,1,{"business":"Example Studio","stage":"proposal","value":"2000"})
        self.c.execute("UPDATE sales_pipeline_leads SET updated_at=? WHERE id=?",
                       (int(time.time())-16*86400,self.lead))
        self.action=sovereign_ascension.action(self.c,1,self.lead,"stalled_deal","approved","Manual review")
        self.wid=ascension_workflows.create(self.c,1,self.action)
    def tearDown(self):
        self.c.close()
    def test_tenant_isolation(self):
        with self.assertRaises(ValueError):
            ascension_workflows.transition(self.c,2,self.wid,"advance","Not my workflow")
        self.assertEqual(self.c.execute("SELECT current_step FROM ascension_workflows WHERE id=?",
                                        (self.wid,)).fetchone()[0],0)
    def test_advance_and_cancel(self):
        self.assertEqual(ascension_workflows.transition(self.c,1,self.wid,"advance","Reviewed manually"),"active")
        self.assertEqual(self.c.execute("SELECT current_step FROM ascension_workflows WHERE id=?",
                                        (self.wid,)).fetchone()[0],1)
        self.assertEqual(ascension_workflows.transition(self.c,1,self.wid,"cancel","Stop"),"cancelled")
        with self.assertRaises(ValueError):
            ascension_workflows.transition(self.c,1,self.wid,"advance","Too late")
    def test_final_step_requires_outcome(self):
        self.c.execute("UPDATE ascension_workflows SET current_step=3 WHERE id=?",(self.wid,))
        with self.assertRaises(ValueError) as cm:
            ascension_workflows.transition(self.c,1,self.wid,"advance","Manual completion")
        self.assertIn("Record the outcome",str(cm.exception))
        self.assertEqual(self.c.execute("SELECT status FROM ascension_workflows WHERE id=?",
                                        (self.wid,)).fetchone()[0],"active")

if __name__=="__main__":
    unittest.main()
