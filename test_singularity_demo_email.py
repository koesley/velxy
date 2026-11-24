import unittest
from demo_leads import format_email_body

class DemoConversionTests(unittest.TestCase):
    def test_clear_optional_registration(self):
        shared = dict(accepted=2, rejected=0, stats=['Example summary'], monthly_rows=[], product_rows=[])
        body = format_email_body(shared, 'https://example.com/demo/abc', 'https://example.com/')
        for phrase in ('1 free report', 'https://example.com/register', 'claim this demo from your dashboard', 'without registering', 'https://example.com/demo/abc'):
            self.assertIn(phrase.lower(), body.lower())
