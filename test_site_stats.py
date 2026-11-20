"""Analytics security and portable day-bucketing regression tests."""
import sqlite3
import unittest
import site_stats


class SiteStatsTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        site_stats.ensure(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_day_grouping_uses_integer_buckets(self):
        site_stats.record(self.conn, 'landing_view', created=2000000000)
        site_stats.record(self.conn, 'landing_view', created=2000000050)
        totals, daily, recent = site_stats.summary(self.conn, days=36500)
        self.assertEqual(totals['landing_view'], 2)
        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0][1]['landing_view'], 2)
        self.assertEqual(daily[0][0] % 86400, 0)

    def test_html_escapes_event_details(self):
        payload = '<img src=x onerror=alert(1)>'
        site_stats.record(self.conn, 'landing_view', payload)
        page = site_stats.stats_html(*site_stats.summary(self.conn))
        self.assertNotIn(payload, page)
        self.assertIn('&lt;img', page)
        self.assertNotIn('<img src=x', page)

    def test_html_escapes_unknown_event_names(self):
        site_stats.record(self.conn, '<script>alert(1)</script>', 'unknown')
        page = site_stats.stats_html(*site_stats.summary(self.conn))
        self.assertNotIn('<script>', page)


if __name__ == '__main__':
    unittest.main()
