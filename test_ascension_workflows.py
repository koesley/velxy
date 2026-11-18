import sqlite3
import unittest
import sales_pipeline
import sovereign_ascension as asc
import ascension_recovery as recovery
import ascension_workflows as wf

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.lead=sales_pipeline.save(self.c,1,{"business":"Example Cafe","email":"hello@example.com","stage":"proposal"})
        self.action=asc.action(self.c,1,self.lead,"stalled_deal","approved")
    def tearDown(self):self.c.close()
    def test_creation_requires_approval(self):
        with self.assertRaises(ValueError):wf.create(self.c,2,self.action)
    def test_duplicate_plan_denied(self):
        wf.create(self.c,1,self.action)
        with self.assertRaises(ValueError):wf.create(self.c,1,self.action)
    def test_audit_and_review_step(self):
        wid=wf.create(self.c,1,self.action)
        self.assertEqual(wf.transition(self.c,1,wid,"advance","Reviewed evidence"),"active")
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM ascension_workflow_events WHERE owner_id=1 AND workflow_id=?",(wid,)).fetchone()[0],2)
    def test_contact_verification_gate(self):
        wid=wf.create(self.c,1,self.action)
        wf.transition(self.c,1,wid,"advance","Reviewed")
        with self.assertRaises(ValueError):wf.transition(self.c,1,wid,"advance","Drafted")
    def test_opt_out_cannot_be_bypassed(self):
        wid=wf.create(self.c,1,self.action)
        wf.transition(self.c,1,wid,"advance","Reviewed")
        sales_pipeline.set_suppression(self.c,1,"hello@example.com","do_not_contact")
        with self.assertRaises(ValueError):wf.transition(self.c,1,wid,"advance","Drafted")
    def test_completion_requires_action_and_outcome(self):
        wid=wf.create(self.c,1,self.action)
        sales_pipeline.set_suppression(self.c,1,"hello@example.com","verified_clear","Current public contact evidence")
        wf.transition(self.c,1,wid,"advance","Reviewed")
        wf.transition(self.c,1,wid,"advance","Draft ready")
        with self.assertRaises(ValueError):wf.transition(self.c,1,wid,"advance","Contacted")
        asc.action(self.c,1,self.lead,"stalled_deal","completed","Manually contacted")
        wf.transition(self.c,1,wid,"advance","Action completed")
        with self.assertRaises(ValueError):wf.transition(self.c,1,wid,"advance","Done")
        recovery.record(self.c,1,self.action,"responded","0","Customer replied")
        self.assertEqual(wf.transition(self.c,1,wid,"advance","Outcome recorded"),"completed")
    def test_cross_owner_cannot_advance(self):
        wid=wf.create(self.c,1,self.action)
        with self.assertRaises(ValueError):wf.transition(self.c,2,wid,"advance","Not mine")
    def test_cancel_is_terminal(self):
        wid=wf.create(self.c,1,self.action)
        self.assertEqual(wf.transition(self.c,1,wid,"cancel","Not relevant"),"cancelled")
        with self.assertRaises(ValueError):wf.transition(self.c,1,wid,"advance","Attempt")
    def test_first_visit(self):
        empty=sqlite3.connect(":memory:")
        try:self.assertIn("Workflow Orchestrator",wf.dashboard(empty,2,"csrf"))
        finally:empty.close()
if __name__=="__main__":unittest.main()
