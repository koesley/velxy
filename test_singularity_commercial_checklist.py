import unittest
import site_stats

class CommercialChecklistTests(unittest.TestCase):
    def test_missing_report_and_payment_stages(self):
        page = site_stats.stats_html({}, [(0, {'landing_view': 4, 'demo_run': 2, 'signup': 1})], [])
        self.assertIn('Test first-report onboarding', page)
        self.assertIn('Reconcile verified settlements', page)
        self.assertNotIn('Verify public accessibility and test', page)
        self.assertIn('not confirmed failures', page)

    def test_all_stages_observed(self):
        page = site_stats.stats_html({}, [(0, dict.fromkeys(site_stats.FUNNEL, 1))], [])
        self.assertIn('Review verified revenue and customer feedback.</li>', page)
