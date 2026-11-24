import unittest
from demo_leads import format_email_body

class EmailGuidanceTests(unittest.TestCase):
    def test_guidance_matches_report_counts(self):
        for accepted, rejected, phrase in [(3,1,'Review flagged records'),(3,0,'Compare monthly and product summaries'),(0,0,'Upload sales records')]:
            shared = dict(accepted=accepted,rejected=rejected,stats=[],monthly_rows=[],product_rows=[])
            body = format_email_body(shared,'https://example.com/demo/a','https://example.com')
            self.assertIn('Recommended next step:',body)
            self.assertIn(phrase,body)
