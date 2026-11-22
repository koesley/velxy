import unittest
from first_value_guide_v78 import Milestone, guide

class GuideTests(unittest.TestCase):
    def test_new_customer(self):
        r = guide("recover_sales", [])
        self.assertEqual(r["completed_steps"], 0)
        self.assertEqual(r["next_action"], "Import or add one lead")
        self.assertFalse(r["first_value_verified"])
    def test_progress(self):
        r = guide("save_time", [Milestone("step_1", True, True)])
        self.assertEqual(r["completed_steps"], 1)
        self.assertEqual(r["next_action"], "Create a draft workflow")
    def test_unverified_not_value(self):
        r = guide("understand_business", [Milestone(f"step_{i}", True) for i in range(1,4)])
        self.assertIsNone(r["next_action"])
        self.assertFalse(r["first_value_verified"])
    def test_verified(self):
        r = guide("recover_sales", [Milestone(f"step_{i}", True, True) for i in range(1,4)])
        self.assertTrue(r["first_value_verified"])
    def test_invalid_goal(self):
        with self.assertRaises(ValueError): guide("unknown", [])
    def test_duplicate(self):
        with self.assertRaises(ValueError): guide("save_time", [Milestone("step_1", True), Milestone("step_1", True)])
    def test_invalid_flags(self):
        with self.assertRaises(ValueError): guide("save_time", [Milestone("step_1", 1)])
    def test_unknown_step(self):
        with self.assertRaises(ValueError): guide("save_time", [Milestone("step_4", True)])

if __name__ == "__main__":
    unittest.main()
