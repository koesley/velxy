"""Regression tests for evidence-aware bounce classification and CRM compatibility."""
import unittest
from outreach_deliverability import (
    bounce_evidence, classify_bounce, summarize_bounces,
    eligible_for_new_outreach, valid_email,
)


class BounceEvidenceReviewTests(unittest.TestCase):
    def test_permanent_recipient_failure(self):
        self.assertEqual(classify_bounce("Diagnostic-Code: smtp; 550 5.1.1 User unknown"), "suppress_permanent")

    def test_rejected_policy(self):
        self.assertEqual(classify_bounce("Status: 5.4.1 recipient address rejected"), "suppress_rejected")

    def test_temporary_dsn_is_held(self):
        self.assertEqual(classify_bounce("Status: 4.2.2 mailbox temporarily full"), "hold_for_verification")

    def test_unknown_and_missing_are_reviewed(self):
        for body in ("", None, "A sales pitch without delivery diagnostics", 123):
            self.assertEqual(classify_bounce(body), "needs_manual_review")

    def test_permanent_overrides_temporary(self):
        self.assertEqual(classify_bounce("4.2.2 retry; final 550 5.1.1"), "suppress_permanent")

    def test_explanation_has_no_customer_content(self):
        status, explanation = bounce_evidence("550 5.1.1 secret@example.com")
        self.assertEqual(status, "suppress_permanent")
        self.assertNotIn("secret@example.com", explanation)

    def test_summary_deduplicates_strictest_and_skips_malformed(self):
        rows = [
            None, {"recipient": 12, "body": "550 5.1.1"},
            {"recipient": "Test@Example.com", "body": "4.2.2"},
            {"recipient": "test@example.com", "body": "550 5.1.1"},
            {"recipient": "bad@", "body": "550 5.1.1"},
        ]
        self.assertEqual(summarize_bounces(rows), {"test@example.com": "suppress_permanent"})

    def test_eligibility_fails_closed_for_invalid_inputs(self):
        self.assertFalse(eligible_for_new_outreach(None, {}))
        self.assertFalse(eligible_for_new_outreach("x@example.com", None))
        self.assertFalse(eligible_for_new_outreach("bad@", {"bad@": "verified_clear"}))
        self.assertTrue(eligible_for_new_outreach(" X@Example.com ", {"x@example.com": "verified_clear"}))

    def test_valid_email_not_proof_of_consent(self):
        self.assertTrue(valid_email("person@example.com"))
        self.assertFalse(eligible_for_new_outreach("person@example.com", {}))


if __name__ == "__main__":
    unittest.main()
