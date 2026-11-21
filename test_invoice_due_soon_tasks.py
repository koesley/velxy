"""Regression tests for opt-in invoice due-soon task workflow."""
import time
import sqlite3
import unittest
from unittest.mock import patch
import business_v4

class DueSoonTaskTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        self.db.execute("INSERT INTO users VALUES (1)")
        self.db.execute("CREATE TABLE vx3_contacts (id TEXT PRIMARY KEY, user_id INTEGER, name TEXT, stage TEXT, created_at INTEGER)")
        self.db.execute("CREATE TABLE vx3_entries (id TEXT PRIMARY KEY, user_id INTEGER, kind TEXT, description TEXT, amount_cents INTEGER, created_at INTEGER)")
        self.db.execute("CREATE TABLE vx3_tasks (id TEXT PRIMARY KEY, user_id INTEGER, title TEXT, status TEXT, created_at INTEGER)")
        business_v4.setup(self.db)
        self.db.execute("INSERT INTO vx4_invoices(id,user_id,description,amount_cents,status,due_at,created_at) VALUES (?,?,?,?,?,?,?)",
                        ("invoice1",1,"Consulting",12500,"issued",2000000000,2000000000))
        self.fixed = 2000000000
        self.today = self.fixed - self.fixed % 86400
        self.db.execute("UPDATE vx4_invoices SET due_at=? WHERE id='invoice1'", (self.today,))

    def tearDown(self):
        self.db.close()

    def run_action(self):
        with patch.object(business_v4.time, "time", return_value=self.fixed):
            business_v4.process(self.db, 1, {"action": "invoice_due_soon_tasks"})

    def test_opt_in_only_and_idempotent(self):
        self.assertEqual(self.db.execute("SELECT count(*) FROM vx3_tasks").fetchone()[0], 0)
        self.run_action()
        self.run_action()
        self.assertEqual(self.db.execute("SELECT count(*) FROM vx3_tasks").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM vx4_events WHERE event_type='due_soon_task'").fetchone()[0], 1)

    def test_due_window_and_tenant_isolation(self):
        self.db.execute("INSERT INTO users VALUES (2)")
        for ident, owner, due in [
            ("late",1,self.today-86400), ("edge",1,self.today+7*86400),
            ("inside",1,self.today+6*86400), ("other",2,self.today)]:
            self.db.execute("INSERT INTO vx4_invoices(id,user_id,description,amount_cents,status,due_at,created_at) VALUES (?,?,?,?,?,?,?)",
                            (ident,owner,"Test",100,"issued",due,self.fixed))
        self.run_action()
        titles=[r[0] for r in self.db.execute("SELECT title FROM vx3_tasks ORDER BY title")]
        self.assertEqual(titles, ["Invoice due soon [inside]", "Invoice due soon [invoice1]"])

    def test_paid_invoice_closes_only_matching_task(self):
        self.run_action()
        self.db.execute("INSERT INTO vx3_tasks VALUES (?,?,?,?,?)",("personal",1,"Personal reminder","open",self.fixed))
        with patch.object(business_v4.time, "time", return_value=self.fixed):
            business_v4.process(self.db,1,{"action":"invoice_pay","id":"invoice1"})
        self.assertEqual(self.db.execute("SELECT status FROM vx3_tasks WHERE title='Invoice due soon [invoice1]'").fetchone()[0],"done")
        self.assertEqual(self.db.execute("SELECT status FROM vx3_tasks WHERE id='personal'").fetchone()[0],"open")

    def test_void_invoice_closes_due_soon_task(self):
        self.run_action()
        business_v4.process(self.db,1,{"action":"invoice_void","id":"invoice1"})
        self.assertEqual(self.db.execute("SELECT status FROM vx3_tasks WHERE title='Invoice due soon [invoice1]'").fetchone()[0],"done")

    def test_dashboard_has_explicit_opt_in(self):
        with patch.object(business_v4.time, "time", return_value=self.fixed):
            page=business_v4.render(self.db,1,"safe-token")
        self.assertIn('value="invoice_due_soon_tasks"',page)
        self.assertIn("No customer messages are sent",page)
        self.assertIn('value="safe-token"',page)

if __name__ == "__main__":
    unittest.main()
