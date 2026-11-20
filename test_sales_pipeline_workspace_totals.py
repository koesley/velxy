"""Workspace-wide sales metrics must not be limited by the 200-lead preview."""
import sqlite3
import unittest
import sales_pipeline


class PipelineWorkspaceTotalsTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        sales_pipeline.setup(self.db)

    def tearDown(self):
        self.db.close()

    def add(self, owner, stage, value, index):
        return sales_pipeline.save(self.db, owner, {
            "business": "Business %d" % index,
            "stage": stage,
            "value": str(value),
        })

    def test_full_workspace_counts_beyond_preview(self):
        for i in range(230):
            self.add(1, "proposal", 100, i)
        page = sales_pipeline.dashboard(self.db, 1, "csrf-token")
        self.assertIn("230 total leads", page)
        self.assertIn("200 shown", page)
        self.assertIn("Estimated open opportunities: $23000", page)
        self.assertIn("Workspace totals include every lead", page)
        self.assertEqual(page.count("<details><summary>Edit lead</summary>"), 200)

    def test_won_and_lost_are_not_open_revenue(self):
        self.add(1, "won", 500, 1)
        self.add(1, "lost", 900, 2)
        self.add(1, "replied", 300, 3)
        page = sales_pipeline.dashboard(self.db, 1, "csrf-token")
        self.assertIn("Self-reported won deals: $500", page)
        self.assertIn("Estimated open opportunities: $300", page)
        self.assertIn("1 replied", page)
        self.assertIn("1 won", page)

    def test_owner_isolation_even_with_many_other_leads(self):
        for i in range(215):
            self.add(2, "won", 10000, i)
        self.add(1, "new", 12, 999)
        page = sales_pipeline.dashboard(self.db, 1, "csrf-token")
        self.assertIn("1 total leads", page)
        self.assertIn("Estimated open opportunities: $12", page)
        self.assertIn("Self-reported won deals: $0", page)
        self.assertNotIn("Business 0", page)

    def test_empty_workspace(self):
        page = sales_pipeline.dashboard(self.db, 1, "csrf-token")
        self.assertIn("0 total leads", page)
        self.assertIn("0 shown", page)
        self.assertIn("Estimated open opportunities: $0", page)

    def test_user_content_is_escaped(self):
        sales_pipeline.save(self.db, 1, {"business": "<script>unsafe</script>"})
        page = sales_pipeline.dashboard(self.db, 1, "csrf-token")
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)


if __name__ == "__main__":
    unittest.main()
