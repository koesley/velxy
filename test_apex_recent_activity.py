import unittest
import site_stats

class RecentActivityTests(unittest.TestCase):
    def test_recent_window_separate_from_lifetime(self):
        page = site_stats.stats_html({'signup': 100}, [(0, {'signup': 2}), (86400, {'signup': 3})], [])
        self.assertIn('Recent commercial activity', page)
        self.assertIn('Accounts created: 5</li>', page)
        self.assertIn('not distinct customers or verified revenue', page)
