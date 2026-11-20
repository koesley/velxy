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

    def test_afternoon_and_late_night_remain_on_same_utc_day(self):
        # PostgreSQL CAST(float AS INTEGER) rounds; integer division must
        # not send afternoon events into the following UTC day.
        midnight = 2000000000 - (2000000000 % 86400)
        for seconds in (1, 43201, 86399):
            site_stats.record(self.conn, 'landing_view', created=midnight + seconds)
        _, daily, _ = site_stats.summary(self.conn, days=36500)
        self.assertEqual(daily, [(midnight, {'landing_view': 3})])

    def test_failed_analytics_write_preserves_business_transaction(self):
        self.conn.execute("CREATE TABLE business_orders (id INTEGER PRIMARY KEY)")
        self.conn.execute("INSERT INTO business_orders VALUES (1)")
        # Simulate an analytics-only database failure.
        self.conn.execute("DROP TABLE site_events")
        self.conn.execute(
            "CREATE TABLE site_events (created INTEGER NOT NULL, event TEXT NOT NULL "
            "CHECK (event='never'), detail TEXT NOT NULL)"
        )
        site_stats.record(self.conn, 'landing_view')
        self.conn.execute("INSERT INTO business_orders VALUES (2)")
        self.conn.commit()
        self.assertEqual(self.conn.execute(
            "SELECT count(*) FROM business_orders"
        ).fetchone()[0], 2)

    def test_successful_analytics_stays_in_caller_transaction(self):
        self.conn.execute("BEGIN")
        site_stats.record(self.conn, 'landing_view')
        self.assertEqual(self.conn.execute(
            "SELECT count(*) FROM site_events"
        ).fetchone()[0], 1)
        self.conn.rollback()
        self.assertEqual(self.conn.execute(
            "SELECT count(*) FROM site_events"
        ).fetchone()[0], 0)

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
