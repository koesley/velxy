import unittest
import site_stats

class FunnelTruthTests(unittest.TestCase):
    def test_repeat_events_not_presented_as_customer_conversion(self):
        page = site_stats.stats_html({'landing_view': 2, 'demo_run': 3}, [], [])
        self.assertIn('150.0%', page)
        self.assertIn('Event count ratio', page)
        self.assertIn('not unique customer conversions', page)
