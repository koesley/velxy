"""Regression tests for complete, owner-scoped sales pipeline metrics."""
import sqlite3
import unittest
from unittest.mock import patch
import sales_pipeline


class PipelineMetricsTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        sales_pipeline.setup(self.conn)

    def tearDown(self):
        self.conn.close()

    def add(self, owner, stage, amount, index):
        self.conn.execute(
            """INSERT INTO sales_pipeline_leads
            (id,owner_id,business,contact,email,industry,stage,estimated_value,notes,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (f"{owner}-{index}",owner,f"Business {index}","","","","" + stage,amount,"",index,index))

    def test_counts_include_rows_beyond_display_limit_and_exclude_other_owners(self):
        for i in range(240):
            self.add(1,"proposal",100,i)
        self.add(1,"won",300,241)
        self.add(2,"won",999999,242)
        with patch.object(sales_pipeline,"outreach_deliverability",sales_pipeline.outreach_deliverability):
            page=sales_pipeline.dashboard(self.conn,1,"csrf-token")
        self.assertIn("241 total leads",page)
        self.assertIn("200 most recently updated displayed",page)
        self.assertIn("Estimated open opportunities: $24000",page)
        self.assertIn("Self-reported won deals: $300",page)
        self.assertIn("Proposal: 240 leads / $24000 estimated",page)
        self.assertNotIn("999999",page)

    def test_empty_and_closed_pipeline(self):
        page=sales_pipeline.dashboard(self.conn,1,"csrf")
        self.assertIn("0 total leads",page)
        self.add(1,"lost",500,1)
        self.add(1,"won",200,2)
        page=sales_pipeline.dashboard(self.conn,1,"csrf")
        self.assertIn("Estimated open opportunities: $0",page)
        self.assertIn("Won: 1 leads / $200 estimated",page)

    def test_escapes_user_entered_business(self):
        sales_pipeline.save(self.conn,1,{"business":"<script>alert(1)</script>","stage":"new","value":"10"})
        page=sales_pipeline.dashboard(self.conn,1,"csrf")
        self.assertNotIn("<script>",page)
        self.assertIn("&lt;script&gt;",page)


if __name__ == "__main__":
    unittest.main()
