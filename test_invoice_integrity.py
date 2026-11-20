"""Revenue integrity tests for repeated invoice payments and overdue reminders."""
import sqlite3
import time
import unittest

import business_v4


class InvoiceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        self.db.execute("INSERT INTO users VALUES (1)")
        self.db.execute("CREATE TABLE vx3_contacts (id TEXT PRIMARY KEY, user_id INTEGER, stage TEXT)")
        self.db.execute("CREATE TABLE vx3_entries (id TEXT PRIMARY KEY, user_id INTEGER, kind TEXT, description TEXT, amount_cents INTEGER, created_at INTEGER)")
        self.db.execute("CREATE TABLE vx3_tasks (id TEXT PRIMARY KEY, user_id INTEGER, title TEXT, status TEXT, created_at INTEGER)")
        business_v4.setup(self.db)
        self.db.execute(
            "INSERT INTO vx4_invoices(id,user_id,description,amount_cents,status,due_at,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("invoice1", 1, "Consulting", 12500, "issued", int(time.time()) - 100, int(time.time()) - 1000),
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_payment_records_income_only_once(self):
        business_v4.process(self.db, 1, {"action": "invoice_pay", "id": "invoice1"})
        with self.assertRaises(ValueError):
            business_v4.process(self.db, 1, {"action": "invoice_pay", "id": "invoice1"})
        self.assertEqual(self.db.execute("SELECT count(*) FROM vx3_entries").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT amount_cents FROM vx3_entries").fetchone()[0], 12500)
        self.assertEqual(self.db.execute("SELECT count(*) FROM vx4_events WHERE event_type='paid'").fetchone()[0], 1)

    def test_repeated_reminders_create_one_task(self):
        for _ in range(3):
            business_v4.process(self.db, 1, {"action": "invoice_reminders"})
        self.assertEqual(self.db.execute("SELECT count(*) FROM vx3_tasks").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM vx4_events WHERE event_type='overdue_task'").fetchone()[0], 1)

    def test_void_invoice_cannot_create_overdue_reminder(self):
        business_v4.process(self.db, 1, {"action": "invoice_void", "id": "invoice1"})
        business_v4.process(self.db, 1, {"action": "invoice_reminders"})
        self.assertEqual(self.db.execute("SELECT count(*) FROM vx3_tasks").fetchone()[0], 0)

    def test_issue_and_void_require_current_status(self):
        with self.assertRaises(ValueError):
            business_v4.process(self.db, 1, {"action": "invoice_issue", "id": "invoice1"})
        business_v4.process(self.db, 1, {"action": "invoice_void", "id": "invoice1"})
        with self.assertRaises(ValueError):
            business_v4.process(self.db, 1, {"action": "invoice_void", "id": "invoice1"})
        self.assertEqual(self.db.execute(
            "SELECT status FROM vx4_invoices WHERE id='invoice1'"
        ).fetchone()[0], "void")

    def test_paid_invoice_cannot_create_overdue_reminder(self):
        business_v4.process(self.db, 1, {"action": "invoice_pay", "id": "invoice1"})
        business_v4.process(self.db, 1, {"action": "invoice_reminders"})
        self.assertEqual(self.db.execute("SELECT count(*) FROM vx3_tasks").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
