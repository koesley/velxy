import unittest
from outreach_copy import Prospect, draft, classify_reply

class OutreachCopyTests(unittest.TestCase):
    def test_header_injection_rejected(self):
        for value in ("Acme\\r\\nBcc: attacker@example.test", "Shop\\x00Name", "A" * 121):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    draft(Prospect(value, "retail"))

    def test_personalization_bounds_and_control_characters(self):
        cases = [
            Prospect("Shop", "retail", first_name="Joe\\nBcc: test"),
            Prospect("Shop", "retail", verified_observation="x" * 501,
                     observation_source="official site"),
            Prospect("Shop", "retail", verified_observation="claim",
                     observation_source="a" * 301),
        ]
        for prospect in cases:
            with self.subTest(prospect=prospect):
                with self.assertRaises(ValueError):
                    draft(prospect)

    def test_opt_out_synonyms_override_interest(self):
        for message in ("I'm interested but take me off your list",
                        "No more emails please", "Don't contact me",
                        "I want to opt-out"):
            self.assertEqual(classify_reply(message), "do_not_contact")

    def test_quoted_opt_out_not_treated_as_current_reply(self):
        self.assertEqual(classify_reply(
            "Please send details\\nOn Monday, Alice wrote:\\n> unsubscribe"),
            "potential_interest")
        self.assertEqual(classify_reply(
            "Sounds good\\n> stop emailing"), "needs_review")

    def test_negative_interest_and_reply_validation(self):
        self.assertEqual(classify_reply("Not right now"), "declined")
        self.assertEqual(classify_reply("Not interested"), "declined")
        self.assertEqual(classify_reply("Interested? No thanks"), "declined")
        with self.assertRaises(ValueError):
            classify_reply(None)

    def test_drafts_remain_manual_and_preserve_normal_fields(self):
        result = draft(Prospect("  Cafe North  ", "restaurant",
                                first_name="  Sam  ",
                                verified_observation="Online menu available",
                                observation_source="Public menu"), "personal")
        self.assertIn("Hi Sam,", result["body"])
        self.assertIn("Cafe North", result["subject"])
        self.assertTrue(result["requires_human_review"])

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

    def test_decline_guidance(self):
        from outreach_copy import reply_guidance
        result = reply_guidance("We have someone else doing the fix")
        self.assertEqual(result["classification"], "declined")
        self.assertEqual(result["suggested_reply"], "")
        self.assertFalse(result["automatic_send"])

    def test_opt_out_guidance(self):
        from outreach_copy import reply_guidance
        result = reply_guidance("Please unsubscribe, not interested")
        self.assertEqual(result["classification"], "do_not_contact")

    def test_quality_warnings(self):
        from outreach_copy import quality_check
        prospect = Prospect("Local Shop", "retail")
        result = quality_check(prospect, draft(prospect))
        self.assertEqual(len(result["warnings"]), 2)
        self.assertFalse(result["send_automatically"])

if __name__ == "__main__":
    unittest.main()
