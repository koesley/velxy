"""Founder funnel integrity tests: python -m unittest test_site_stats_integrity -v."""
import sqlite3
import time
import unittest
from unittest.mock import patch
import site_stats


class FounderIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        site_stats.ensure(self.conn)
        self.addCleanup(self.conn.close)

    def test_unrecognized_event_never_enters_log(self):
        site_stats.record(self.conn, 'secret_email', 'someone@example.test')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM site_events').fetchone()[0], 0)

    def test_html_escapes_detail_and_unknown_event(self):
        page = site_stats.stats_html({}, [], [(0, '<script>', '<img src=x onerror=alert(1)>')])
        self.assertNotIn('<script>', page)
        self.assertNotIn('<img', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('&lt;img', page)

    def test_funnel_does_not_invent_conversion(self):
        page = site_stats.stats_html({'landing_view': 1, 'demo_run': 12}, [], [])
        self.assertIn('Not measured', page)
        self.assertNotIn('1200.0%', page)
        self.assertIn('not unique-user conversion rates', page)

    def test_calendar_days_include_zeros_and_today(self):
        now = 1763596800  # 2025-11-20 00:00 UTC
        with patch.object(site_stats.time, 'time', return_value=now):
            site_stats.record(self.conn, 'landing_view', created=now - 86400)
            totals, daily, recent = site_stats.summary(self.conn, days=3)
        self.assertEqual(len(daily), 3)
        self.assertEqual([d for d, _ in daily], [now - 2*86400, now-86400, now])
        self.assertEqual(daily[0][1], {})
        self.assertEqual(daily[1][1]['landing_view'], 1)
        self.assertEqual(daily[2][1], {})

    def test_utc_boundary_excludes_previous_calendar_day(self):
        now = 1763596800
        with patch.object(site_stats.time, 'time', return_value=now):
            site_stats.record(self.conn, 'demo_run', created=now - 1)
            site_stats.record(self.conn, 'demo_run', created=now)
            _, daily, _ = site_stats.summary(self.conn, days=1)
        self.assertEqual(daily[0][1]['demo_run'], 1)

    def test_rejects_unbounded_days(self):
        for value in (0, -1, 91, 1.5, True, '14'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                site_stats.summary(self.conn, days=value)

    def test_recent_detail_is_escaped_and_known_event_rendered(self):
        site_stats.record(self.conn, 'demo_run', '<b>bad</b>')
        _, daily, recent = site_stats.summary(self.conn)
        page = site_stats.stats_html({}, daily, recent)
        self.assertIn('&lt;b&gt;bad&lt;/b&gt;', page)
        self.assertNotIn('<b>bad</b>', page)


if __name__ == '__main__':
    unittest.main()
