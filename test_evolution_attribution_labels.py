import unittest
from decimal import Decimal


class AttributionLabelTests(unittest.TestCase):
    def test_report_distinguishes_association_from_causation(self):
        import portal
        report = dict(has_data=True, week_label='This week', top_move='Review sales', revenue_this_week=Decimal('100'), orders_this_week=1, revenue_last_week=Decimal('0'), top_products=[], quiet_customers=[], latest_report=None)
        html = portal.money_report_html(report, (2, 1, Decimal('100')))
        self.assertIn('Customers marked contacted: 2', html)
        self.assertIn('Customers with later paid orders: 1', html)
        self.assertIn('does not establish that outreach caused them', html)
        self.assertNotIn(' recovered.</p>', html)
        self.assertNotIn('Customers marked contacted', portal.money_report_html(report, (0, 0, Decimal('0'))))
