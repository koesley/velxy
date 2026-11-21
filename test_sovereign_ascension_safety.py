"""Isolated security regressions for the live Sovereign Ascension action engine.

Run: python -m unittest -v test_sovereign_ascension_safety
Uses in-memory SQLite; never connects to production or sends messages.
"""
import sqlite3
import unittest
import sovereign_ascension
import sales_pipeline


class AscensionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        sales_pipeline.setup(self.c)
        sovereign_ascension.setup(self.c)
        self.c.execute(
            """INSERT INTO sales_pipeline_leads
            (id,owner_id,business,contact,email,industry,stage,estimated_value,
             notes,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            ("lead-a", 1, "Alpha", "A", "alpha@example.com", "services",
             "proposal", 50000, "", 1, 1),
        )
        self.c.execute(
            """INSERT INTO sales_pipeline_leads
            (id,owner_id,business,contact,email,industry,stage,estimated_value,
             notes,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            ("lead-b", 2, "Beta", "B", "beta@example.com", "services",
             "proposal", 90000, "", 1, 1),
        )
        self.c.commit()

    def tearDown(self):
        self.c.close()

    def test_requires_current_evidence_and_owner(self):
        with self.assertRaises(ValueError):
            sovereign_ascension.action(self.c, 1, "lead-b", "stalled_deal", "approved")
        with self.assertRaises(ValueError):
            sovereign_ascension.action(self.c, 1, "lead-a", "aging_lead", "approved")
        self.c.execute("UPDATE sales_pipeline_leads SET stage='won' WHERE id='lead-a'")
        with self.assertRaises(ValueError):
            sovereign_ascension.action(self.c, 1, "lead-a", "stalled_deal", "approved")

    def test_suppressed_lead_has_no_approval_button(self):
        self.c.execute(
            "INSERT INTO outreach_suppression VALUES (?,?,?,?,?)",
            (1,"alpha@example.com","do_not_contact","customer opted out",1))
        page=sovereign_ascension.dashboard(self.c,1,"csrf")
        self.assertIn("Approval blocked:",page)
        self.assertNotIn('value="approved"',page)
        self.assertIn('value="dismissed"',page)

    def test_clear_lead_retains_approval_option(self):
        page=sovereign_ascension.dashboard(self.c,1,"csrf")
        self.assertIn('value="approved"',page)
        self.assertNotIn("Approval blocked:",page)

    def test_suppression_blocks_approval(self):
        self.c.execute(
            "INSERT INTO outreach_suppression VALUES (?,?,?,?,?)",
            (1, "alpha@example.com", "do_not_contact", "opt out", 1),
        )
        with self.assertRaises(ValueError):
            sovereign_ascension.action(self.c, 1, "lead-a", "stalled_deal", "approved")
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM ascension_actions").fetchone()[0], 0)

    def test_one_approval_and_documented_completion(self):
        ident=sovereign_ascension.action(self.c, 1, "lead-a", "stalled_deal", "approved")
        with self.assertRaises(ValueError):
            sovereign_ascension.action(self.c, 1, "lead-a", "stalled_deal", "approved")
        with self.assertRaises(ValueError):
            sovereign_ascension.action(self.c, 1, "lead-a", "stalled_deal", "completed", "done")
        self.assertEqual(
            sovereign_ascension.action(self.c, 1, "lead-a", "stalled_deal", "completed",
                                       "Follow-up reviewed and recorded"),
            ident,
        )
        with self.assertRaises(ValueError):
            sovereign_ascension.action(self.c, 1, "lead-a", "stalled_deal", "completed",
                                       "Repeated completion attempt")

    def test_decision_events_record_approval_and_completion(self):
        action_id=sovereign_ascension.action(
            self.c, 1, "lead-a", "stalled_deal", "approved", "Review next steps")
        sovereign_ascension.action(
            self.c, 1, "lead-a", "stalled_deal", "completed",
            "Reviewed the customer response")
        events=self.c.execute(
            "SELECT event_type,note,action_id FROM ascension_action_events "
            "WHERE owner_id=? ORDER BY created_at,id",(1,)).fetchall()
        self.assertEqual(len(events),2)
        self.assertEqual({event[0] for event in events},{"approved","completed"})
        self.assertTrue(all(event[2]==action_id for event in events))
        page=sovereign_ascension.dashboard(self.c,1,"csrf")
        self.assertIn("Decision audit trail",page)
        self.assertIn("Reviewed the customer response",page)
        self.assertNotIn("Private Beta",page)

    def test_failed_decision_writes_no_audit_event(self):
        self.c.execute(
            "INSERT INTO outreach_suppression VALUES (?,?,?,?,?)",
            (1,"alpha@example.com","do_not_contact","opt out",1))
        with self.assertRaises(ValueError):
            sovereign_ascension.action(
                self.c,1,"lead-a","stalled_deal","approved")
        self.assertEqual(
            self.c.execute("SELECT COUNT(*) FROM ascension_action_events").fetchone()[0],0)

    def test_audit_trail_escapes_untrusted_notes(self):
        sovereign_ascension.action(
            self.c,1,"lead-a","stalled_deal","dismissed",
            '<img src=x onerror="alert(1)">')
        page=sovereign_ascension.dashboard(self.c,1,"csrf")
        self.assertNotIn('<img src=x',page)
        self.assertIn('&lt;img src=x',page)

    def test_dismissed_signal_cannot_be_approved_later(self):
        sovereign_ascension.action(self.c, 1, "lead-a", "stalled_deal", "dismissed")
        with self.assertRaises(ValueError):
            sovereign_ascension.action(self.c, 1, "lead-a", "stalled_deal", "approved")


if __name__ == "__main__":
    unittest.main()
