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
        self.db.execute("CREATE TABLE vx3_contacts (id TEXT PRIMARY KEY, user_id INTEGER, name TEXT, stage TEXT)")
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

    def test_due_soon_forecast_excludes_overdue_paid_and_other_tenants(self):
        from unittest.mock import patch
        fixed = 2000000000
        self.db.execute("INSERT INTO users VALUES (2)")
        cases = [
            ("due1", 1, 3200, "issued", fixed+86400),
            ("due2", 1, 4800, "issued", fixed+6*86400),
            ("later", 1, 50000, "issued", fixed+8*86400),
            ("paid", 1, 90000, "paid", fixed+86400),
            ("foreign", 2, 999999, "issued", fixed+86400),
        ]
        for ident,uid,cents,status,due in cases:
            self.db.execute(
                "INSERT INTO vx4_invoices(id,user_id,description,amount_cents,status,due_at,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (ident,uid,ident,cents,status,due,fixed-100)
            )
        with patch.object(business_v4.time, "time", return_value=fixed):
            page=business_v4.render(self.db, 1, "csrf")
        self.assertIn("Due within 7 days",page)
        self.assertIn("$80.00",page)
        self.assertIn("across 2 issued invoices",page)
        self.assertIn("due1",page)
        self.assertIn("due2",page)
        self.assertNotIn("foreign",page)

    def test_aging_dashboard_separates_overdue_buckets_and_tenants(self):
        from unittest.mock import patch
        fixed = 2000000000
        self.db.execute("UPDATE vx4_invoices SET due_at=? WHERE id='invoice1'",
                        (fixed-3*86400,))
        self.db.execute("INSERT INTO users VALUES (2)")
        cases = [
            ("eight", 1, 2500, fixed-10*86400),
            ("thirty", 1, 7000, fixed-40*86400),
            ("other_tenant", 2, 999999, fixed-50*86400),
        ]
        for ident, uid, cents, due in cases:
            self.db.execute(
                "INSERT INTO vx4_invoices(id,user_id,description,amount_cents,status,due_at,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (ident, uid, "Test", cents, "issued", due, fixed-100)
            )
        with patch.object(business_v4.time, "time", return_value=fixed):
            page = business_v4.render(self.db, 1, "csrf")
        self.assertIn("$125.00", page)
        self.assertIn("$25.00", page)
        self.assertIn("$70.00", page)
        self.assertNotIn("$9,999.99", page)
        self.assertIn("1–7 days overdue", page)
        self.assertIn("8–30 days overdue", page)
        self.assertIn("Over 30 days overdue", page)

    def test_overdue_query_uses_tenant_status_due_index(self):
        plan = self.db.execute(
            "EXPLAIN QUERY PLAN SELECT id FROM vx4_invoices "
            "WHERE user_id=? AND status='issued' AND due_at<?",
            (1, int(time.time()))
        ).fetchall()
        self.assertTrue(any("vx4_invoices_due" in str(row) for row in plan), plan)

    def test_other_tenant_cannot_pay_or_void_invoice(self):
        self.db.execute("INSERT INTO users VALUES (2)")
        for action in ("invoice_pay", "invoice_void", "invoice_issue"):
            with self.assertRaises(ValueError):
                business_v4.process(self.db, 2, {"action": action, "id": "invoice1"})
        self.assertEqual(self.db.execute(
            "SELECT status FROM vx4_invoices WHERE id='invoice1'"
        ).fetchone()[0], "issued")
        self.assertEqual(self.db.execute("SELECT count(*) FROM vx3_entries").fetchone()[0], 0)

    def test_rollback_does_not_record_partial_payment(self):
        self.db.execute("BEGIN")
        business_v4.process(self.db, 1, {"action": "invoice_pay", "id": "invoice1"})
        self.db.rollback()
        self.assertEqual(self.db.execute(
            "SELECT status FROM vx4_invoices WHERE id='invoice1'"
        ).fetchone()[0], "issued")
        self.assertEqual(self.db.execute("SELECT count(*) FROM vx3_entries").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM vx4_events").fetchone()[0], 0)

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
