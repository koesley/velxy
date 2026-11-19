"""Regression tests for founder analytics data integrity and HTML safety."""
import sqlite3
import time
import unittest

import site_stats


class AnalyticsTrustTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        site_stats.ensure(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_rejects_unknown_events_without_storing_them(self):
        site_stats.record(self.conn, 'not_a_real_event', '<script>bad</script>')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM site_events').fetchone()[0], 0)

    def test_escapes_untrusted_detail_in_founder_html(self):
        site_stats.record(self.conn, 'demo_run', '<img src=x onerror=alert(1)>')
        totals, daily, recent = site_stats.summary(self.conn)
        page = site_stats.stats_html(totals, daily, recent)
        self.assertNotIn('<img src=x', page)
        self.assertIn('&lt;img src=x', page)

    def test_escapes_legacy_unknown_event_and_detail(self):
        self.conn.execute(
            'INSERT INTO site_events(created,event,detail) VALUES(?,?,?)',
            (int(time.time()), '<svg onload=alert(1)>', '<script>bad</script>'))
        totals, daily, recent = site_stats.summary(self.conn)
        self.assertEqual(recent, [])
        self.assertNotIn('<svg', site_stats.stats_html(totals, daily, recent))

    def test_limits_details_and_strips_null_bytes(self):
        site_stats.record(self.conn, 'signup', 'a' * 400 + '\x00')
        detail = self.conn.execute('SELECT detail FROM site_events').fetchone()[0]
        self.assertEqual(len(detail), 240)
        self.assertNotIn('\x00', detail)

    def test_summary_rejects_unbounded_windows(self):
        for days in (0, -1, 91, True, '14'):
            with self.subTest(days=days), self.assertRaises(ValueError):
                site_stats.summary(self.conn, days=days)

    def test_funnel_is_labeled_event_ratio_not_user_conversion(self):
        html = site_stats.stats_html({'landing_view': 1, 'demo_run': 2}, [], [])
        self.assertIn('not unique people or cohort conversion', html)
        self.assertIn('200.0%', html)

    def test_preserves_known_event_counts(self):
        site_stats.record(self.conn, 'landing_view')
        site_stats.record(self.conn, 'demo_run')
        totals, daily, recent = site_stats.summary(self.conn)
        self.assertEqual(totals['landing_view'], 1)
        self.assertEqual(totals['demo_run'], 1)
        self.assertEqual(len(recent), 2)


if __name__ == '__main__':
    unittest.main()
