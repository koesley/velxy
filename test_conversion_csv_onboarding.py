"""Regression coverage for public CSV onboarding and plan clarity."""
import csv
import io
import os
import tempfile
import unittest
import urllib.parse
from unittest.mock import patch

class ConversionOnboardingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.env = patch.dict(os.environ, {'VELXTRIA_DATA_DIR': cls.tmp.name,
            'VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT': '0'})
        cls.env.start()
        import portal
        cls.portal = portal

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.tmp.cleanup()

    def test_template_headers_match_upload_contract(self):
        p = self.portal
        url = p.demo_csv_template_url()
        self.assertTrue(url.startswith('data:text/csv;charset=utf-8,'))
        rows = list(csv.reader(io.StringIO(urllib.parse.unquote(url.split(',', 1)[1]))))
        self.assertEqual(rows[0], p.REQUIRED)
        self.assertEqual(len(rows[1]), len(p.REQUIRED))
        self.assertEqual(rows[1][0], 'VX-001')

    def test_template_escapes_csv_fields_correctly(self):
        p = self.portal
        with patch.object(p, 'REQUIRED', ['A,quoted', 'B"quoted']):
            url = p.demo_csv_template_url()
            rows = list(csv.reader(io.StringIO(urllib.parse.unquote(url.split(',', 1)[1]))))
        self.assertEqual(rows[0], ['A,quoted', 'B"quoted'])

    def test_landing_guide_is_integrated_and_actionable(self):
        body = self.portal.landing_page()
        self.assertIn('id="v8-start-guide"', body)
        self.assertIn('download="velxtria_sales_template.csv"', body)
        self.assertIn('href="#try"', body)
        self.assertIn('href="/register"', body)
        self.assertLess(body.index('id="v8-start-guide"'), body.index('id="try"'))

    def test_pricing_and_safety_disclosures(self):
        body = self.portal.landing_page()
        self.assertIn('$49 per 30 days', body)
        self.assertIn('Bitcoin only', body)
        self.assertIn('payment verification', body)
        self.assertIn('sample or non-sensitive', body)
        self.assertIn('fictional example data', body)

    def test_header_text_escaped_in_guide(self):
        p = self.portal
        with patch.object(p, 'REQUIRED', ['<script>alert(1)</script>']):
            guide = p.landing_preflight_html()
        self.assertNotIn('<script>', guide)
        self.assertIn('&lt;script&gt;', guide)

if __name__ == '__main__':
    unittest.main()
