"""Contact decision audit: tenant isolation, safe rendering, bounded history."""
import sqlite3
import unittest
from sales_pipeline import dashboard, setup

class ContactDecisionAuditTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        setup(self.db)

    def tearDown(self):
        self.db.close()

    def event(self, owner, email, reason, when=100):
        self.db.execute(
            "INSERT INTO outreach_suppression_events "
            "(owner_id,email,status,reason,created_at) VALUES (?,?,?,?,?)",
            (owner,email,"hold_for_verification",reason,when))

    def test_account_isolation(self):
        self.event(1,"mine@example.com","my reason")
        self.event(2,"other@example.com","private reason")
        page=dashboard(self.db,1,"csrf")
        self.assertIn("mine@example.com",page)
        self.assertNotIn("other@example.com",page)
        self.assertNotIn("private reason",page)

    def test_escapes_untrusted_evidence(self):
        self.event(1,"a@example.com","<script>alert('x')</script>")
        page=dashboard(self.db,1,"csrf")
        self.assertNotIn("<script>",page)
        self.assertIn("&lt;script&gt;",page)

    def test_empty_history(self):
        page=dashboard(self.db,1,"csrf")
        self.assertIn("No decisions recorded yet.",page)

    def test_bounded_and_total_count(self):
        for i in range(35):
            self.event(1,f"item{i}@example.com",str(i),i)
        page=dashboard(self.db,1,"csrf")
        self.assertIn("Latest 30 of 35 recorded decisions",page)
        self.assertIn("item34@example.com",page)
        self.assertNotIn("item0@example.com",page)

    def test_read_only(self):
        self.event(1,"a@example.com","review")
        before=self.db.total_changes
        dashboard(self.db,1,"csrf")
        self.assertEqual(self.db.total_changes,before)

if __name__ == "__main__":
    unittest.main()
