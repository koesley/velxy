"""Regression checks for saved draft eligibility and safe revision."""
import sqlite3
import unittest
from unittest.mock import patch
import ascension_followups as studio


class DraftReadinessTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE ascension_followup_drafts (id TEXT, owner_id INTEGER, action_id TEXT, lead_id TEXT, recipient TEXT, subject TEXT, body TEXT, status TEXT, created_at INTEGER, updated_at INTEGER)")
        self.c.execute("CREATE TABLE ascension_actions (id TEXT, owner_id INTEGER, status TEXT)")
        self.c.execute("CREATE TABLE sales_pipeline_leads (id TEXT, owner_id INTEGER, email TEXT, stage TEXT)")
        self.c.execute("INSERT INTO ascension_actions VALUES ('a',1,'approved')")
        self.c.execute("INSERT INTO sales_pipeline_leads VALUES ('l',1,'hello@example.com','proposal')")
        self.c.execute("INSERT INTO ascension_followup_drafts VALUES ('d',1,'a','l','hello@example.com','Hi','Message','draft',0,0)")
        self.eligibility = patch("ascension_followups.sales_pipeline.outreach_eligibility", return_value=True)
        self.eligibility.start()

    def tearDown(self):
        self.eligibility.stop()
        self.c.close()

    def test_ready_and_cross_owner_denial(self):
        self.assertTrue(studio.draft_readiness(self.c,1,"d")[0])
        self.assertFalse(studio.draft_readiness(self.c,2,"d")[0])

    def test_revoked_action_blocks_draft(self):
        self.c.execute("UPDATE ascension_actions SET status='rejected'")
        self.assertFalse(studio.draft_readiness(self.c,1,"d")[0])

    def test_changed_email_blocks_draft(self):
        self.c.execute("UPDATE sales_pipeline_leads SET email='other@example.com'")
        self.assertEqual(studio.draft_readiness(self.c,1,"d")[1],"Lead email has changed")

    def test_closed_lead_blocks_draft(self):
        self.c.execute("UPDATE sales_pipeline_leads SET stage='won'")
        self.assertFalse(studio.draft_readiness(self.c,1,"d")[0])

    def test_suppressed_contact_blocks_draft(self):
        with patch("ascension_followups.sales_pipeline.outreach_eligibility", return_value=False):
            self.assertFalse(studio.draft_readiness(self.c,1,"d")[0])

    @patch("ascension_followups.setup")
    def test_revise_rejects_newline_subject_and_nontext(self, setup):
        for subject, body in [("Hello" + chr(10) + "Bcc: victim@example.com","body"), (None,"body"), ("Hello",None)]:
            with self.assertRaises(ValueError):
                studio.revise(self.c,1,"d",subject,body)

    @patch("ascension_followups.setup")
    def test_revise_rechecks_action_and_preserves_saved_text(self, setup):
        self.c.execute("UPDATE ascension_actions SET status='rejected'")
        with self.assertRaises(ValueError):
            studio.revise(self.c,1,"d","New subject","New body")
        self.assertEqual(self.c.execute("SELECT subject,body FROM ascension_followup_drafts WHERE id='d'").fetchone(),("Hi","Message"))


if __name__ == "__main__":
    unittest.main()
