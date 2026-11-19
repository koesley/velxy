import sqlite3
import unittest
from unittest.mock import patch

import sales_pipeline as sp


class AtomicSuppressionImportTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        sp.setup(self.db)

    def tearDown(self):
        self.db.close()

    def status(self, owner, email):
        row = self.db.execute(
            "SELECT status FROM outreach_suppression WHERE owner_id=? AND email=?",
            (owner, email)).fetchone()
        return row[0] if row else None

    def test_duplicate_recipient_prefers_stricter_status(self):
        with patch.object(sp.outreach_deliverability, "classify_bounce",
                          side_effect=["hold_for_verification", "suppress_permanent"]):
            count = sp.import_bounce_lines(
                self.db, 1, "a@example.com | temporary error\na@example.com | permanent error")
        self.assertEqual(count, 2)
        self.assertEqual(self.status(1, "a@example.com"), "suppress_permanent")
        events = self.db.execute("SELECT COUNT(*) FROM outreach_suppression_events").fetchone()[0]
        self.assertEqual(events, 1)

    def test_invalid_later_row_does_not_mutate(self):
        with self.assertRaises(ValueError):
            sp.import_bounce_lines(self.db, 1, "a@example.com | 550 no user\ninvalid")
        self.assertIsNone(self.status(1, "a@example.com"))

    def test_mid_batch_write_failure_rolls_back(self):
        self.db.execute("""CREATE TRIGGER reject_second BEFORE INSERT ON outreach_suppression
            WHEN NEW.email='b@example.com' BEGIN SELECT RAISE(ABORT, 'blocked'); END""")
        with self.assertRaises(sqlite3.DatabaseError):
            sp.import_bounce_lines(self.db, 1,
                "a@example.com | 550 user unknown\nb@example.com | 550 user unknown")
        self.assertIsNone(self.status(1, "a@example.com"))
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM outreach_suppression_events").fetchone()[0], 0)

    def test_owner_isolation_and_existing_opt_out(self):
        sp.set_suppression(self.db, 1, "a@example.com", "do_not_contact", "asked to stop")
        sp.import_bounce_lines(self.db, 2, "a@example.com | 550 no such user")
        self.assertEqual(self.status(1, "a@example.com"), "do_not_contact")
        self.assertIsNotNone(self.status(2, "a@example.com"))

    def test_gmail_import_uses_same_atomic_path(self):
        notice = "Your message wasn't delivered to a@example.com\n550 user unknown"
        self.assertEqual(sp.import_gmail_notices(self.db, 1, notice), 1)
        self.assertIsNotNone(self.status(1, "a@example.com"))

    def test_existing_permanent_suppression_never_downgraded(self):
        sp.set_suppression(self.db, 1, "a@example.com", "suppress_permanent", "hard bounce")
        with patch.object(sp.outreach_deliverability, "classify_bounce",
                          return_value="hold_for_verification"):
            sp.import_bounce_lines(self.db, 1, "a@example.com | temporary error")
        self.assertEqual(self.status(1, "a@example.com"), "suppress_permanent")


if __name__ == "__main__":
    unittest.main()
