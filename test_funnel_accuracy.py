"""Regression coverage for honest funnel reporting and UTC analytics windows."""
import sqlite3
import time
import unittest
from unittest.mock import patch
import site_stats


class FunnelAccuracyTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        site_stats.ensure(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_event_counts_are_not_claimed_as_user_conversions(self):
        site_stats.record(self.conn, 'landing_view', created=2000000000)
        for _ in range(3):
            site_stats.record(self.conn, 'demo_run', created=2000000000)
        page = site_stats.stats_html(*site_stats.summary(self.conn, days=36500))
        self.assertIn('not unique visitors or cohort conversions', page)
        self.assertNotIn('300.0%', page)
        self.assertIn('Demo reports generated', page)

    def test_daily_window_includes_today_and_excludes_future(self):
        now = 2000000000
        midnight = now // 86400 * 86400
        with patch.object(site_stats.time, 'time', return_value=now):
            for created in (midnight - 86400, midnight, midnight + 86399,
                            midnight + 86400):
                site_stats.record(self.conn, 'demo_run', created=created)
            totals, daily, _ = site_stats.summary(self.conn, days=2)
        self.assertEqual(totals['demo_run'], 4)
        self.assertEqual(daily, [
            (midnight - 86400, {'demo_run': 1}),
            (midnight, {'demo_run': 2}),
        ])

    def test_invalid_day_windows_fail_closed(self):
        for value in (0, -1, 36501, True, 1.5, '14'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                site_stats.summary(self.conn, days=value)

    def test_event_details_remain_escaped(self):
        site_stats.record(self.conn, 'demo_run', '<script>bad()</script>')
        page = site_stats.stats_html(*site_stats.summary(self.conn))
        self.assertNotIn('<script>bad()</script>', page)
        self.assertIn('&lt;script&gt;', page)


if __name__ == '__main__':
    unittest.main()
