import unittest
from site_stats import checkout_health, checkout_health_html

class CheckoutHealthTests(unittest.TestCase):
    def test_unavailable_priority(self):
        counts, action = checkout_health([(0, {'checkout_unavailable':2,'checkout_failed':3})])
        self.assertEqual(counts['checkout_unavailable'],2)
        self.assertIn('configuration',action)
    def test_failure(self):
        self.assertIn('creation errors',checkout_health([(0,{'checkout_failed':1})])[1])
    def test_empty(self):
        self.assertIn('paid offer',checkout_health([])[1])
    def test_activation_gap(self):
        self.assertIn('settlements',checkout_health([(0,{'checkout_started':3})])[1])
    def test_aggregate_not_buyers(self):
        self.assertIn('not unique buyers',checkout_health_html([]))
