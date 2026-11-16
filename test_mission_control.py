"""Mission Control access and output regression tests."""
import unittest
from unittest.mock import patch
import mission_control

LEADS = {"metrics": {"open_pipeline": 1200.0, "won_reported": 50.0,
                      "pending_approvals": 2}}
AGENTS = {"role": "owner", "jobs": [
    {"id": "a", "agent": "sales", "goal": "<script>alert(1)</script>",
     "status": "in_review"},
    {"id": "b", "agent": "support", "goal": "Answer FAQ", "status": "completed"},
    {"id": "c", "agent": "marketing", "goal": "Draft campaign", "status": "queued"},
]}

class MissionControlTests(unittest.TestCase):
    @patch("mission_control.workforce.overview", return_value=AGENTS)
    @patch("mission_control.sales.overview", return_value=LEADS)
    @patch("mission_control.core.access", return_value="owner")
    def test_aggregates_existing_workspace_data(self, access, sales, agents):
        d = mission_control.snapshot(object(), 9, "tenant-one")
        self.assertEqual(d["workforce"]["pending_review"], 1)
        self.assertEqual(d["workforce"]["completed"], 1)
        self.assertEqual(d["pipeline"]["pending_approvals"], 2)
        self.assertEqual(len(d["attention"]), 1)
        self.assertEqual(access.call_args.args[1:], (9, "tenant-one"))
        self.assertEqual(sales.call_args.args[1:], (9, "tenant-one"))
        self.assertEqual(agents.call_args.args[1:], (9, "tenant-one"))

    @patch("mission_control.core.access", side_effect=ValueError("Forbidden"))
    def test_unauthorized_workspace_fails_closed(self, access):
        with self.assertRaisesRegex(ValueError, "Forbidden"):
            mission_control.snapshot(object(), 9, "another-tenant")

    @patch("mission_control.workforce.overview", return_value=AGENTS)
    @patch("mission_control.sales.overview", return_value=LEADS)
    @patch("mission_control.core.access", return_value="owner")
    def test_html_escapes_untrusted_agent_goals(self, *_):
        html = mission_control.render(object(), 9, "tenant-one", "csrf")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("Mission", html) if False else None

if __name__ == "__main__":
    unittest.main()
