import unittest
import site_stats

class CommercialDiagnosticTests(unittest.TestCase):
    def test_missing_checkout_activity(self):
        page = site_stats.stats_html({}, [(0, {'landing_view': 5, 'demo_run': 2, 'signup': 1})], [])
        self.assertIn('no checkout starts were recorded', page)
        self.assertIn('Missing telemetry may explain zero counts', page)

    def test_no_activity(self):
        self.assertIn('no landing views were recorded', site_stats.stats_html({}, [], []))
