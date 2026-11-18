"""Regression tests for actionable report observations."""
import unittest
from report_insights import insights, render

MONTHS = [['Month','Paid Orders','Paid Revenue'],['2026-10','3','470.00'],['2026-11','2','330.00']]
PRODUCTS = [['Product','Paid Orders','Paid Revenue'],['Cleaning','4','650.00'],['Other','1','150.00']]

class ReportInsightsTests(unittest.TestCase):
    def test_data_quality_and_revenue_change(self):
        result = ' '.join(insights(MONTHS, PRODUCTS, 6, 3))
        self.assertIn('3 of 9', result)
        self.assertIn('29.8% lower', result)
        self.assertIn('81.2%', result)

    def test_html_escaping_and_no_script(self):
        products = [['Product','Paid Orders','Paid Revenue'],['<script>alert(1)</script>','1','100']]
        html = render(MONTHS, products, 1, 0)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_zero_previous_month_no_division(self):
        months = [['Month','Paid Orders','Paid Revenue'],['2026-10','0','0'],['2026-11','1','20']]
        self.assertIn('not meaningful', ' '.join(insights(months, PRODUCTS, 1, 0)))

    def test_malformed_and_negative_values_ignored(self):
        months = [['Month','Paid Orders','Paid Revenue'],['2026-10','1','NaN'],['2026-11','-1','-4']]
        products = [['Product','Paid Orders','Paid Revenue'],['Bad','1','Infinity']]
        text = ' '.join(insights(months, products, 0, 0))
        self.assertNotIn('Product concentration', text)
        self.assertIn('No source rows', text)

    def test_missing_headers_fail_closed(self):
        self.assertEqual(len(insights([['oops']], [['oops']], 1, 0)), 2)

if __name__ == '__main__':
    unittest.main()
