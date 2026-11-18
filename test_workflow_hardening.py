"""Regression checks for owner isolation and stale workflow transitions."""
import sqlite3
import os
import persistent
import time
import unittest
import sales_pipeline
import sovereign_ascension
import ascension_workflows

class WorkflowHardeningTests(unittest.TestCase):
    def setUp(self):
        if os.getenv("VELXTRIA_TEST_POSTGRES")=="1":
            from urllib.parse import urlparse
            dbname=urlparse(os.getenv("VELXTRIA_DATABASE_URL","")).path.lstrip("/")
            if dbname != "velxtria_test":
                raise RuntimeError("PostgreSQL tests require the dedicated velxtria_test database")
        self.c=persistent.connect(":memory:") if os.getenv("VELXTRIA_TEST_POSTGRES")=="1" else sqlite3.connect(":memory:")
        # PostgreSQL service is shared across tests; clean only these test-owned tables.
        if os.getenv("VELXTRIA_TEST_POSTGRES")=="1":
            for table in ("ascension_workflow_events","ascension_workflows",
                          "ascension_recovery_outcomes","ascension_actions",
                          "outreach_suppression_events","outreach_suppression",
                          "sales_pipeline_leads"):
                self.c.execute("DROP TABLE IF EXISTS "+table)
            self.c.commit()
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
    def test_duplicate_workflow_creation_rejected(self):
        with self.assertRaises(ValueError):
            ascension_workflows.create(self.c,1,self.action)
        self.assertEqual(self.c.execute(
            "SELECT COUNT(*) FROM ascension_workflows WHERE owner_id=? AND action_id=?",
            (1,self.action)).fetchone()[0],1)

    def test_other_owner_cannot_cancel(self):
        with self.assertRaises(ValueError):
            ascension_workflows.transition(self.c,2,self.wid,"cancel","Unauthorized")
        self.assertEqual(self.c.execute(
            "SELECT status FROM ascension_workflows WHERE id=?",
            (self.wid,)).fetchone()[0],"active")
        self.assertEqual(self.c.execute(
            "SELECT COUNT(*) FROM ascension_workflow_events WHERE owner_id=? AND workflow_id=?",
            (2,self.wid)).fetchone()[0],0)

    def test_cancelled_workflow_cannot_be_cancelled_twice(self):
        self.assertEqual(ascension_workflows.transition(self.c,1,self.wid,"cancel","Stop"),"cancelled")
        with self.assertRaises(ValueError):
            ascension_workflows.transition(self.c,1,self.wid,"cancel","Duplicate request")
        self.assertEqual(self.c.execute(
            "SELECT COUNT(*) FROM ascension_workflow_events WHERE owner_id=? AND workflow_id=? AND event='cancelled'",
            (1,self.wid)).fetchone()[0],1)

    def test_unverified_contact_blocks_draft_progression(self):
        self.assertEqual(ascension_workflows.transition(
            self.c,1,self.wid,"advance","Reviewed proposal"),"active")
        with self.assertRaisesRegex(ValueError,"suppressed or not verified"):
            ascension_workflows.transition(
                self.c,1,self.wid,"advance","Attempt without clearance")
        self.assertEqual(self.c.execute(
            "SELECT current_step FROM ascension_workflows WHERE id=?",
            (self.wid,)).fetchone()[0],1)

    def test_do_not_contact_blocks_progress_after_prior_clearance(self):
        self.c.execute("UPDATE sales_pipeline_leads SET email=? WHERE id=?",
                       ("blocked@example.com",self.lead))
        sales_pipeline.set_suppression(
            self.c,1,"blocked@example.com","verified_clear",
            "Verified on current publicly available business contact page")
        self.assertEqual(ascension_workflows.transition(
            self.c,1,self.wid,"advance","Reviewed proposal"),"active")
        sales_pipeline.set_suppression(
            self.c,1,"blocked@example.com","do_not_contact","Recipient opted out")
        with self.assertRaisesRegex(ValueError,"suppressed or not verified"):
            ascension_workflows.transition(
                self.c,1,self.wid,"advance","Attempt after opt out")
        with self.assertRaises(ValueError):
            sales_pipeline.set_suppression(
                self.c,1,"blocked@example.com","verified_clear",
                "Trying to override previously recorded opt out")

    def test_unverified_payment_is_not_counted_as_received_revenue(self):
        import ascension_recovery
        sovereign_ascension.action(
            self.c,1,self.lead,"stalled_deal","completed","Manual follow-up")
        ascension_recovery.record(
            self.c,1,self.action,"payment_reported","2000.00",
            "Customer reported payment verbally; no settlement verification")
        outcome=self.c.execute(
            "SELECT outcome,amount_cents FROM ascension_recovery_outcomes WHERE owner_id=? AND action_id=?",
            (1,self.action)).fetchone()
        self.assertEqual(tuple(outcome),("payment_reported",200000))
        page=ascension_recovery.dashboard(self.c,1,"csrf-test")
        self.assertIn("user-reported payments",page)
        self.assertIn("NOT verified payment receipts",page)

    def test_stalled_proposal_signal_is_evidence_based(self):
        # A separate, unapproved CRM record must appear in the discovery queue.
        other=sales_pipeline.save(self.c,1,{"business":"Second Prospect","stage":"proposal","value":"2000"})
        self.c.execute("UPDATE sales_pipeline_leads SET updated_at=? WHERE id=?",
                       (int(time.time())-16*86400,other))
        items=sovereign_ascension.discover(self.c,1)
        item=next(x for x in items if x["lead_id"]==other)
        self.assertEqual(item["kind"],"stalled_deal")
        self.assertEqual(item["estimated_value"],2000)
        self.assertEqual(item["days"],16)
        self.assertIn("CRM stage: proposal",item["evidence"])
        self.assertFalse(any(x["lead_id"]==other for x in sovereign_ascension.discover(self.c,2)))

    def test_complete_customer_recovery_lifecycle(self):
        import ascension_recovery
        # Explicitly clear the test contact; no messages are sent.
        self.c.execute("UPDATE sales_pipeline_leads SET email=? WHERE id=?",
                       ("owner@example.com",self.lead))
        sales_pipeline.set_suppression(
            self.c,1,"owner@example.com","verified_clear",
            "Verified from an independently reviewed business contact page")
        signals=sovereign_ascension.discover(self.c,1)
        # An already-approved opportunity is intentionally omitted from the new queue.
        self.assertFalse(any(item["lead_id"]==self.lead for item in signals))
        self.assertEqual(self.c.execute(
            "SELECT estimated_value FROM sales_pipeline_leads WHERE id=? AND owner_id=?",
            (self.lead,1)).fetchone()[0],2000)
        self.assertEqual(ascension_workflows.transition(self.c,1,self.wid,"advance","Reviewed proposal"),"active")
        self.assertEqual(ascension_workflows.transition(self.c,1,self.wid,"advance","Prepared manual draft"),"active")
        with self.assertRaises(ValueError):
            ascension_workflows.transition(self.c,1,self.wid,"advance","Not yet completed")
        sovereign_ascension.action(self.c,1,self.lead,"stalled_deal","completed","Follow-up completed manually")
        self.assertEqual(ascension_workflows.transition(self.c,1,self.wid,"advance","Manual follow-up confirmed"),"active")
        with self.assertRaises(ValueError):
            ascension_workflows.transition(self.c,1,self.wid,"advance","Outcome missing")
        with self.assertRaises(ValueError):
            ascension_recovery.record(self.c,2,self.action,"responded","0","Other owner")
        ascension_recovery.record(self.c,1,self.action,"responded","0","Customer responded manually")
        self.assertEqual(ascension_workflows.transition(self.c,1,self.wid,"advance","Recorded outcome"),"completed")
        self.assertEqual(tuple(self.c.execute(
            "SELECT outcome,amount_cents FROM ascension_recovery_outcomes WHERE owner_id=? AND action_id=?",
            (1,self.action)).fetchone()),("responded",0))
        self.assertEqual(self.c.execute(
            "SELECT COUNT(*) FROM ascension_workflow_events WHERE owner_id=? AND workflow_id=?",
            (1,self.wid)).fetchone()[0],5)

    def test_final_step_requires_outcome(self):
        self.c.execute("UPDATE ascension_workflows SET current_step=3 WHERE id=?",(self.wid,))
        with self.assertRaises(ValueError) as cm:
            ascension_workflows.transition(self.c,1,self.wid,"advance","Manual completion")
        self.assertIn("Record the outcome",str(cm.exception))
        self.assertEqual(self.c.execute("SELECT status FROM ascension_workflows WHERE id=?",
                                        (self.wid,)).fetchone()[0],"active")

if __name__=="__main__":
    unittest.main()
