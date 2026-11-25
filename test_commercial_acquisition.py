import sqlite3
import time
import unittest

import site_stats


class CommercialAcquisitionTests(unittest.TestCase):
    def test_allowlisted_channels(self):
        for channel in site_stats.CAMPAIGN_CHANNELS:
            self.assertEqual(site_stats.campaign_channel('/?utm_medium=' + channel), channel)

    def test_unknown_and_duplicate_values(self):
        for path in ('/?utm_medium=private%40example.com',
                     '/?utm_medium=email&utm_medium=social',
                     '/?utm_medium=email&utm_medium=',
                     '/?utm_medium='):
            self.assertEqual(site_stats.campaign_channel(path), 'other')

    def test_untagged(self):
        self.assertEqual(site_stats.campaign_channel('/?secret=private'), 'untagged')

    def test_reporting_window_and_event_scope(self):
        with sqlite3.connect(':memory:') as conn:
            site_stats.ensure(conn)
            now = int(time.time())
            conn.executemany('INSERT INTO site_events (created,event,detail) VALUES (?,?,?)', [
                (now, 'landing_view', 'email'),
                (now, 'landing_view', 'email'),
                (now - 15 * 86400, 'landing_view', 'email'),
                (now, 'signup', 'email'),
                (now, 'landing_view', 'private@example.com'),
            ])
            panel = site_stats.acquisition_html(conn)
            self.assertIn('<th scope="row">email</th><td>2</td>', panel)
            self.assertNotIn('private@example.com', panel)
            self.assertIn('not unique visitors or attributed sales', panel)


if __name__ == '__main__':
    unittest.main()
