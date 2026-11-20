"""Customer-level receivables regression coverage; no outbound actions."""
import sqlite3
import unittest
from unittest.mock import patch
import business_v4


class CustomerReceivablesTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        self.db.executemany("INSERT INTO users VALUES (?)", [(1,), (2,)])
        self.db.execute("CREATE TABLE vx3_contacts (id TEXT PRIMARY KEY, user_id INTEGER, name TEXT, created_at INTEGER)")
        self.db.execute("CREATE TABLE vx3_entries (id TEXT PRIMARY KEY, user_id INTEGER, kind TEXT, description TEXT, amount_cents INTEGER, created_at INTEGER)")
        self.db.execute("CREATE TABLE vx3_tasks (id TEXT PRIMARY KEY, user_id INTEGER, title TEXT, status TEXT, created_at INTEGER)")
        business_v4.setup(self.db)
        self.db.executemany("INSERT INTO vx3_contacts VALUES (?,?,?,?)", [
            ("a",1,"Acme <script>",1), ("b",1,"Beta",2), ("other",2,"Secret Corp",3)])
        fixed = 2000000000
        self.today = fixed - fixed % 86400
        rows = [
            ("i1",1,"a",10000,"issued",self.today-86400),
            ("i2",1,"a",2500,"issued",self.today+86400),
            ("i3",1,"b",5000,"paid",self.today-86400),
            ("i4",1,None,3000,"issued",self.today-86400),
            ("i5",2,"other",900000,"issued",self.today-86400),
            ("i6",1,"a",900,"void",self.today-86400),
        ]
        self.db.executemany(
            "INSERT INTO vx4_invoices(id,user_id,contact_id,amount_cents,status,due_at,description,created_at) VALUES (?,?,?,?,?,?,?,?)",
            [(i,u,c,a,s,d,"Test",1) for i,u,c,a,s,d in rows])
        self.fixed = fixed

    def tearDown(self):
        self.db.close()

    def render(self, uid=1):
        with patch.object(business_v4.time,"time",return_value=self.fixed):
            return business_v4.render(self.db,uid,"csrf")

    def test_groups_customer_balances_and_excludes_paid_void(self):
        page=self.render()
        self.assertIn("Customers with outstanding invoices",page)
        self.assertIn("$125.00",page)
        self.assertIn("2 ·",page)
        self.assertIn("1 · $100.00",page)
        self.assertNotIn("$50.00",page)

    def test_unlinked_and_escaped_customer_name(self):
        page=self.render()
        self.assertIn("Unlinked customer",page)
        self.assertIn("Acme &lt;script&gt;",page)
        self.assertNotIn("Acme <script>",page)

    def test_other_tenant_is_not_exposed(self):
        page=self.render()
        self.assertNotIn("Secret Corp",page)
        self.assertNotIn("$9,000.00",page)
        other=self.render(2)
        self.assertIn("Secret Corp",other)
        self.assertNotIn("Acme",other)

    def test_due_today_is_not_overdue(self):
        self.db.execute("UPDATE vx4_invoices SET due_at=? WHERE id='i1'",(self.today,))
        page=self.render()
        self.assertIn("0 · $0.00",page)

    def test_empty_workspace(self):
        self.db.execute("DELETE FROM vx4_invoices WHERE user_id=1")
        self.assertIn("No issued invoices recorded.",self.render())


if __name__ == "__main__":
    unittest.main()
