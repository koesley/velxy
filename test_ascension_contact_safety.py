"""Regression coverage for Ascension contact safety and action integrity."""
import sqlite3
import unittest
import sales_pipeline
import sovereign_ascension as asc


class AscensionContactSafetyTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        sales_pipeline.setup(self.db)
        asc.setup(self.db)

    def tearDown(self):
        self.db.close()

    def lead(self, owner=1, email="person@example.com", business="Example Shop"):
        ident = sales_pipeline.save(self.db, owner, {
            "business": business, "email": email, "stage": "proposal", "value": "500"})
        self.db.execute("UPDATE sales_pipeline_leads SET updated_at=? WHERE id=?",
                        (1000000 - 15 * 86400, ident))
        return ident

    def test_suppression_owner_isolation_and_normalization(self):
        self.lead()
        self.db.execute("UPDATE sales_pipeline_leads SET email=? WHERE owner_id=1",
                        (" Person@Example.com ",))
        self.db.execute("INSERT INTO outreach_suppression VALUES (?,?,?,?,?)",
                        (1, "person@example.com", "do_not_contact", "opted out", 1))
        self.db.execute("INSERT INTO outreach_suppression VALUES (?,?,?,?,?)",
                        (2, "person@example.com", "verified_clear", "other tenant", 1))
        item = asc.discover(self.db, 1, at=1000000)[0]
        self.assertTrue(item["contact_blocked"])
        self.assertEqual(item["contact_state"], "do_not_contact")
        self.assertIn("Do not contact", item["recommendation"])
        self.assertEqual(asc.discover(self.db, 2, at=1000000), [])

    def test_missing_email_and_hold_are_distinguished(self):
        self.lead(email="")
        self.lead(email="hold@example.com", business="Second Shop")
        self.db.execute("INSERT INTO outreach_suppression VALUES (?,?,?,?,?)",
                        (1, "hold@example.com", "hold_for_verification", "review", 1))
        items = asc.discover(self.db, 1, at=1000000)
        self.assertEqual({x["contact_state"] for x in items},
                         {"missing_email", "hold_for_verification"})
        self.assertEqual(sum(x["contact_blocked"] for x in items), 1)

    def test_duplicate_approval_is_idempotent(self):
        ident = self.lead()
        first = asc.action(self.db, 1, ident, "stalled_deal", "approved")
        second = asc.action(self.db, 1, ident, "stalled_deal", "approved")
        self.assertEqual(first, second)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM ascension_actions").fetchone()[0], 1)

    def test_note_validation_prevents_oversize_and_control_characters(self):
        ident = self.lead()
        for note in ("x" * 501, "bad\\x00note"):
            with self.subTest(note=repr(note[:15])):
                with self.assertRaises(ValueError):
                    asc.action(self.db, 1, ident, "stalled_deal", "approved", note)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM ascension_actions").fetchone()[0], 0)

    def test_dashboard_discloses_limits_and_restrictions(self):
        self.lead()
        self.db.execute("INSERT INTO outreach_suppression VALUES (?,?,?,?,?)",
                        (1, "person@example.com", "suppress_permanent", "bounce", 1))
        page = asc.dashboard(self.db, 1, "<csrf>")
        self.assertIn("Contact restricted", page)
        self.assertIn("up to 500", page)
        self.assertIn("&lt;csrf&gt;", page)
        self.assertNotIn('value="<csrf>"', page)


if __name__ == "__main__":
    unittest.main()
