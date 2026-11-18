"""Regression coverage for the existing authenticated Revenue Command Center."""
import sqlite3
import unittest
from unittest.mock import patch
import sales_pipeline
import ascension_command_center as center

class RevenueCommandCenterFunnelTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        sales_pipeline.setup(self.db)
        # Keep the test independent of other product subsystems while preserving
        # their real tables and the Command Center's real SQL queries.
        self.db.execute("CREATE TABLE ascension_actions (id TEXT,owner_id INTEGER,status TEXT)")
        self.db.execute("CREATE TABLE ascension_recovery_outcomes (owner_id INTEGER,action_id TEXT,outcome TEXT,amount_cents INTEGER)")
        self.db.execute("CREATE TABLE ascension_followup_drafts (owner_id INTEGER,recipient TEXT,status TEXT)")
        self.patches=[
            patch.object(center.sovereign_ascension,"setup",lambda c:None),
            patch.object(center.ascension_recovery,"setup",lambda c:None),
            patch.object(center.ascension_followups,"setup",lambda c:None),
        ]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.db.close()

    def lead(self,owner,business,stage="new",value=0,email=""):
        return sales_pipeline.save(self.db,owner,dict(business=business,stage=stage,value=str(value),email=email))

    def test_full_dataset_aggregation_beyond_display_cap(self):
        for i in range(215):
            self.lead(1,"Business "+str(i),value=10)
        s=center.snapshot(self.db,1,now=1000000)
        self.assertEqual(s["stage_values"]["new"],2150)
        self.assertEqual(s["stages"]["new"],215)
        self.assertIn("$2150 estimated open value",center.dashboard(self.db,1))

    def test_owner_isolation_and_blocked_contacts(self):
        self.lead(1,"Owner One",value=100,email="stop@example.com")
        self.lead(2,"Owner Two",value=900,email="stop@example.com")
        sales_pipeline.set_suppression(self.db,1,"stop@example.com","do_not_contact")
        first=center.snapshot(self.db,1)
        second=center.snapshot(self.db,2)
        self.assertEqual(first["blocked_open"],1)
        self.assertEqual(second["blocked_open"],0)
        self.assertEqual(first["stage_values"]["new"],100)
        self.assertEqual(second["stage_values"]["new"],900)

    def test_stale_open_excludes_closed_and_recent(self):
        old=self.lead(1,"Old Open")
        closed=self.lead(1,"Old Closed",stage="won")
        self.lead(1,"Recent Open")
        self.db.execute("UPDATE sales_pipeline_leads SET updated_at=1 WHERE id IN (?,?)",(old,closed))
        s=center.snapshot(self.db,1,now=20*86400)
        self.assertEqual(s["stale_open"],1)

    def test_estimated_and_reported_are_distinct(self):
        self.lead(1,"Won Deal",stage="won",value=700)
        s=center.snapshot(self.db,1)
        self.assertEqual(s["stage_values"]["won"],700)
        self.assertEqual(s["reported_cents"],0)
        page=center.dashboard(self.db,1)
        self.assertIn("self-reported won value",page)
        self.assertIn("not verified revenue",page)

    def test_empty_state(self):
        s=center.snapshot(self.db,1)
        self.assertEqual(s["stale_open"],0)
        self.assertEqual(s["blocked_open"],0)
        self.assertEqual(s["stage_values"],{})
        self.assertIn("0 open leads",center.dashboard(self.db,1))

if __name__=="__main__":
    unittest.main()
