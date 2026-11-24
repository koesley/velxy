import unittest
from site_stats import stats_html


class MilestoneRatioTests(unittest.TestCase):
    def test_recent_ratios_ignore_all_time_and_optional_email(self):
        page = stats_html({'landing_view': 999}, [(0, {'landing_view': 10, 'demo_run': 5, 'signup': 2, 'checkout_started': 4, 'pro_activated': 1})], [])
        for expected in ('5 / 10</td><td>50.0%', '2 / 5</td><td>40.0%', '4 / 2</td><td>200.0%', '1 / 4</td><td>25.0%'):
            self.assertIn(expected, page)
        self.assertIn('not customer conversion rates', page)

    def test_empty_window(self):
        page = stats_html({}, [], [])
        self.assertEqual(page.count('0 / 0</td><td>Unavailable'), 4)
