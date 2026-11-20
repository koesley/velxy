"""Regression coverage for sales lead data integrity and workspace isolation."""
import sqlite3
import unittest
import sales_pipeline


class LeadIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        sales_pipeline.setup(self.db)

    def tearDown(self):
        self.db.close()

    def test_valid_lead_and_normalized_email(self):
        lead = sales_pipeline.save(self.db, 10, {
            "business": "Acme Shop", "email": "  OWNER@EXAMPLE.COM  ",
            "contact": "Pat", "value": "250", "stage": "proposal",
        })
        row = self.db.execute(
            "SELECT email,estimated_value,stage FROM sales_pipeline_leads WHERE id=?", (lead,)
        ).fetchone()
        self.assertEqual(row, ("owner@example.com", 250, "proposal"))

    def test_invalid_fields_do_not_create_lead(self):
        base = {"business": "Acme Shop"}
        bad = [
            {"business": "A"},
            {"business": "A" * 121},
            {"notes": "hello\x00world"},
            {"contact": "Pat\nInjected"},
            {"industry": "x" * 81},
            {"email": "not-an-email"},
            {"email": "x@example.com\rBcc:evil@example.com"},
            {"value": "-1"},
            {"value": "1.5"},
            {"value": "9" * 10000},
            {"stage": "invalid"},
        ]
        for changes in bad:
            with self.subTest(changes=str(changes)[:80]):
                with self.assertRaises(ValueError):
                    sales_pipeline.save(self.db, 10, dict(base, **changes))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM sales_pipeline_leads").fetchone()[0], 0)

    def test_invalid_edit_preserves_existing_lead(self):
        lead = sales_pipeline.save(self.db, 10, {"business": "Acme Shop", "notes": "original"})
        with self.assertRaises(ValueError):
            sales_pipeline.save(self.db, 10, {"lead_id": lead, "business": "Changed Shop", "notes": "bad\x7f"})
        self.assertEqual(
            self.db.execute("SELECT business,notes FROM sales_pipeline_leads WHERE id=?", (lead,)).fetchone(),
            ("Acme Shop", "original"),
        )

    def test_cross_workspace_edit_rejected(self):
        lead = sales_pipeline.save(self.db, 10, {"business": "Acme Shop"})
        with self.assertRaises(ValueError):
            sales_pipeline.save(self.db, 11, {"lead_id": lead, "business": "Hijacked"})
        self.assertEqual(
            self.db.execute("SELECT owner_id,business FROM sales_pipeline_leads WHERE id=?", (lead,)).fetchone(),
            (10, "Acme Shop"),
        )

    def test_notes_escape_in_dashboard(self):
        sales_pipeline.save(self.db, 10, {"business": "Acme Shop", "notes": "<script>alert(1)</script>"})
        rendered = sales_pipeline.dashboard(self.db, 10, "csrf")
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)


if __name__ == "__main__":
    unittest.main()
