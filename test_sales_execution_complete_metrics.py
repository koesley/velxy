"""Regression coverage for full-workspace sales execution metrics."""
import sqlite3
import unittest
from unittest.mock import patch

import sales_execution_v44 as sales


class CompleteMetricsTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE vx_growth_strategy42 (id TEXT, workspace_id TEXT, title TEXT)")
        self.db.executemany("INSERT INTO vx_growth_strategy42 VALUES (?,?,?)",
                            [("p-a", "a", "Plan A"), ("p-b", "b", "Plan B")])
        sales.setup(self.db)

    def tearDown(self):
        self.db.close()

    def add(self, workspace, stage, due, number):
        self.db.execute(
            "INSERT INTO vx_sales_actions44 VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (f"{workspace}-{number}", workspace, "p-" + workspace, 1,
             "Prospect", "call", "Follow up", due, stage, 1, 1))

    @patch("sales_execution_v44.bos.core.access")
    def test_full_counts_not_limited_to_preview(self, access):
        for n in range(240):
            self.add("a", "queued", "2026-11-01", n)
        result = sales.snapshot(self.db, 1, "a", today="2026-11-20")
        self.assertEqual(len(result["items"]), 200)
        self.assertEqual(result["total"], 240)
        self.assertEqual(result["open"], 240)
        self.assertEqual(result["overdue"], 240)
        self.assertTrue(result["preview_limited"])

    @patch("sales_execution_v44.bos.core.access")
    def test_stage_and_date_aggregates(self, access):
        for n, (stage, due) in enumerate([
            ("queued", "2026-11-19"), ("contacted", "2026-11-20"),
            ("awaiting_reply", "2026-11-21"), ("won", "2026-11-01"),
            ("lost", "2026-11-01")]):
            self.add("a", stage, due, n)
        result = sales.snapshot(self.db, 1, "a", today="2026-11-20")
        self.assertEqual(tuple(result[k] for k in
            ("total", "open", "overdue", "due_today", "won_marked", "lost_marked")),
            (5, 3, 1, 1, 1, 1))
        self.assertFalse(result["preview_limited"])

    @patch("sales_execution_v44.bos.core.access")
    def test_tenant_isolation_and_empty_workspace(self, access):
        self.add("b", "queued", "2026-11-01", 1)
        result = sales.snapshot(self.db, 1, "a", today="2026-11-20")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["items"], [])
        self.assertEqual(result["overdue"], 0)

    @patch("sales_execution_v44.bos.core.access")
    def test_render_explains_preview_limit(self, access):
        with patch("sales_execution_v44.strategy.analyze", return_value=[]):
            self.db.execute("CREATE TABLE empire_members (workspace_id TEXT, user_id INTEGER)")
            page = sales.render(self.db, 1, "a", "csrf")
        self.assertIn("counts cover the full workspace", page)


if __name__ == "__main__":
    unittest.main()
