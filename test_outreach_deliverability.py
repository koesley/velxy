import unittest
from outreach_deliverability import classify_bounce, summarize_bounces, eligible_for_new_outreach

class DeliverabilityTests(unittest.TestCase):
    def test_invalid_mailbox(self):
        self.assertEqual(classify_bounce("550 5.1.1 User does not exist"),"suppress_permanent")
    def test_timeout(self):
        self.assertEqual(classify_bounce("recipient server timed out"),"hold_for_verification")
    def test_rejected(self):
        self.assertEqual(classify_bounce("550 5.4.1 Recipient address rejected: Access denied"),"suppress_rejected")
    def test_dns(self):
        self.assertEqual(classify_bounce("DNS Error: MX lookup NXDOMAIN"),"hold_for_verification")
    def test_duplicate_precedence(self):
        statuses=summarize_bounces([
            {"recipient":"Info@Example.com","body":"timed out"},
            {"recipient":"info@example.com","body":"550 5.1.1 User does not exist"}])
        self.assertEqual(statuses,{"info@example.com":"suppress_permanent"})
    def test_fail_closed(self):
        self.assertFalse(eligible_for_new_outreach("info@example.com",{}))
        self.assertFalse(eligible_for_new_outreach("info@example.com",{"info@example.com":"hold_for_verification"}))
        self.assertTrue(eligible_for_new_outreach("info@example.com",{"info@example.com":"verified_clear"}))

if __name__=="__main__":
    unittest.main()
