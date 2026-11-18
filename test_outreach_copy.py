import unittest
from outreach_copy import Prospect, draft, classify_reply

class OutreachCopyTests(unittest.TestCase):
    def test_industry_specific(self):
        result = draft(Prospect("Cafe North", "restaurant"), "bold")
        self.assertIn("reservations", result["body"])
        self.assertTrue(result["requires_human_review"])

    def test_no_invented_observation(self):
        with self.assertRaises(ValueError):
            draft(Prospect("Cafe North", "restaurant", verified_observation="Your bookings are declining"))

    def test_sourced_observation(self):
        result = draft(Prospect("Cafe North", "restaurant", verified_observation="Your menu is online", observation_source="official website"))
        self.assertIn("Your menu is online", result["body"])

    def test_opt_out_priority(self):
        self.assertEqual(classify_reply("Not interested. Stop emailing me."), "do_not_contact")
        self.assertEqual(classify_reply("We have someone else doing the fix"), "declined")

    def test_styles(self):
        for style in ("bold", "curious", "personal"):
            self.assertIn("VELXTRIA", draft(Prospect("Shop", "retail"), style)["body"])

if __name__ == "__main__":
    unittest.main()
