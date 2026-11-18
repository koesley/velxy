import sqlite3
import unittest
from unittest.mock import patch
from revenue_priority_live import live_rankings


class LivePrioritiesTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE bos59_leads (id TEXT, workspace_id TEXT, value REAL, status TEXT, updated INTEGER)")
        self.db.executemany("INSERT INTO bos59_leads VALUES (?,?,?,?,?)", [
            ("a", "workspace-1", 1200, "new", 1),
            ("b", "workspace-2", 900000, "contacted", 1),
            ("c", "workspace-1", 300, "won", 1),
            ("d", "workspace-1", 800, "contacted", 1),
        ])

    def tearDown(self):
        self.db.close()

    def test_workspace_scoping_and_closed_lead_exclusion(self):
        with patch("revenue_priority_live.business_os_v59.core.access") as access, patch(
            "revenue_priority_live.business_os_v59.init"
        ):
            rows = live_rankings(self.db, 7, "workspace-1")
        access.assert_called_once_with(self.db, 7, "workspace-1")
        self.assertEqual({x["identifier"] for x in rows}, {"a", "d"})
        self.assertTrue(all(x["requires_approval"] for x in rows))

    def test_access_failure_does_not_return_leads(self):
        with patch("revenue_priority_live.business_os_v59.core.access", side_effect=ValueError("Forbidden")):
            with self.assertRaises(ValueError):
                live_rankings(self.db, 7, "workspace-2")


if __name__ == "__main__":
    unittest.main()
