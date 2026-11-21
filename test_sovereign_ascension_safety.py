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

    def test_dismissed_signal_cannot_be_approved_later(self):
        sovereign_ascension.action(self.c, 1, "lead-a", "stalled_deal", "dismissed")
        with self.assertRaises(ValueError):
            sovereign_ascension.action(self.c, 1, "lead-a", "stalled_deal", "approved")


if __name__ == "__main__":
    unittest.main()
