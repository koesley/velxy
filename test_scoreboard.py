"""Tests for the live landing-page scoreboard: real usage numbers from
the site_events log — demos, reports, rows checked/flagged, paid
revenue — with zero metrics omitted and the section hidden when the
database read fails. The numbers on the page must match the database
counts exactly, and must move when new demos run. Run with:
  python -m unittest test_scoreboard -v
"""
import http.client
import os
import sqlite3
import tempfile
import threading
import unittest
import urllib.parse
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import scoreboard
import site_stats

_TMP = None
_ENV = None


def setUpModule():
    global _TMP, _ENV
    _TMP = tempfile.TemporaryDirectory()
    _ENV = patch.dict(os.environ, {
        'VELXTRIA_DATA_DIR': _TMP.name,
        'VELXTRIA_DEPLOYMENT_MODE': 'local',
        'VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT': '0',
    })
    _ENV.start()
    import portal  # noqa: F401  (imported for its module-level DATA_ROOT)
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


def tearDownModule():
    import portal
    with portal.db() as c:
        c.execute('DELETE FROM site_events')
    _ENV.stop()
    _TMP.cleanup()
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


def _seed(conn, rows):
    site_stats.ensure(conn)
    for event, detail in rows:
        site_stats.record(conn, event, detail)


SEEDED = [
    ('demo_run', 'own=1 accepted=6 rejected=3 paid=80000'),
    ('demo_run', 'sample=1 accepted=6 rejected=3 paid=80000'),
    ('demo_run', 'accepted=2 rejected=1 paid=35000'),
    ('report_generated', 'accepted=10 rejected=2 paid=120000'),
]


class FailingConn:
    """A database connection whose every read fails."""

    def execute(self, *args, **kwargs):
        raise sqlite3.OperationalError('no such table: site_events')


class ScoreboardUnitTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        scoreboard.reset_cache()

    def tearDown(self):
        self.conn.close()
        scoreboard.reset_cache()

    def test_counts_match_seeded_events(self):
        _seed(self.conn, SEEDED)
        stats = scoreboard.compute_stats(self.conn)
        self.assertEqual(stats, {'demos': 3, 'reports': 4, 'rows_checked': 33,
                                 'rows_flagged': 9, 'revenue_cents': 315000})

    def test_zero_metrics_omitted(self):
        import portal
        stats = scoreboard.compute_stats(self.conn)
        self.assertEqual(stats, {'demos': 0, 'reports': 0, 'rows_checked': 0,
                                 'rows_flagged': 0, 'revenue_cents': 0})
        self.assertEqual(scoreboard.scoreboard_items(stats), [])
        self.assertEqual(portal.landing_scoreboard_html(stats), '')

    def test_other_events_ignored(self):
        _seed(self.conn, [('landing_view', ''), ('signup', ''),
                          ('checkout_started', 'order-1')])
        stats = scoreboard.compute_stats(self.conn)
        self.assertEqual(stats['demos'], 0)
        self.assertEqual(stats['reports'], 0)
        self.assertEqual(stats['rows_checked'], 0)

    def test_section_hidden_when_db_read_fails(self):
        import portal
        self.assertIsNone(scoreboard.compute_stats(FailingConn()))
        self.assertIsNone(scoreboard.get_stats(FailingConn()))
        self.assertEqual(portal.landing_scoreboard_html(None), '')
        # A failed read is never cached: a good read right after works.
        _seed(self.conn, SEEDED[:1])
        self.assertEqual(scoreboard.get_stats(self.conn)['demos'], 1)

    def test_counts_change_when_new_demos_run(self):
        _seed(self.conn, SEEDED[:2])
        before = scoreboard.compute_stats(self.conn)
        self.assertEqual((before['demos'], before['rows_checked']), (2, 18))
        _seed(self.conn, [('demo_run', 'accepted=4 rejected=2 paid=10000')])
        after = scoreboard.compute_stats(self.conn)
        self.assertEqual((after['demos'], after['rows_checked'],
                          after['rows_flagged'], after['revenue_cents']),
                         (3, 24, 8, 170000))

    def test_paid_revenue_parsing(self):
        self.assertEqual(scoreboard.paid_cents_from_stats(
            ['Paid revenue (accepted Paid orders only): $800.00']), 80000)
        self.assertEqual(scoreboard.paid_cents_from_stats(
            ['Paid revenue (accepted Paid orders only): $1,234.56']), 123456)
        self.assertEqual(scoreboard.paid_cents_from_stats(
            ['Source rows: 9']), 0)
        self.assertEqual(scoreboard.paid_cents_from_stats(
            ['Paid revenue (accepted Paid orders only): n/a']), 0)
        self.assertEqual(scoreboard.paid_cents_from_stats([]), 0)
        self.assertEqual(scoreboard.paid_cents_from_stats(None), 0)

    def test_cache_and_reset(self):
        _seed(self.conn, SEEDED[:1])
        self.assertEqual(scoreboard.get_stats(self.conn)['demos'], 1)
        _seed(self.conn, SEEDED[1:2])
        # Cached: the second demo is not visible yet.
        self.assertEqual(scoreboard.get_stats(self.conn)['demos'], 1)
        scoreboard.reset_cache()
        self.assertEqual(scoreboard.get_stats(self.conn)['demos'], 2)

    def test_revenue_floored_to_whole_dollars(self):
        items = scoreboard.scoreboard_items(
            {'demos': 0, 'reports': 0, 'rows_checked': 0,
             'rows_flagged': 0, 'revenue_cents': 80050})
        self.assertEqual(items, [('$800', 'in sales checked')])
        items = scoreboard.scoreboard_items(
            {'demos': 0, 'reports': 0, 'rows_checked': 0,
             'rows_flagged': 0, 'revenue_cents': 50})
        self.assertEqual(items, [])

    def test_singular_labels(self):
        items = scoreboard.scoreboard_items(
            {'demos': 1, 'reports': 1, 'rows_checked': 9,
             'rows_flagged': 3, 'revenue_cents': 80000})
        self.assertEqual(items, [('1', 'demo run'), ('1', 'report generated'),
                                 ('9', 'rows checked'),
                                 ('3', 'problem rows flagged'),
                                 ('$800', 'in sales checked')])

    def test_old_details_without_paid_token_still_count(self):
        # Demos recorded before the paid= token existed contribute
        # demos and rows, but no revenue — never a guess.
        _seed(self.conn, [('demo_run', 'accepted=6 rejected=3')])
        stats = scoreboard.compute_stats(self.conn)
        self.assertEqual((stats['demos'], stats['rows_checked'],
                          stats['revenue_cents']), (1, 9, 0))


class ScoreboardFlowTests(unittest.TestCase):
    def setUp(self):
        import portal
        self.portal = portal
        # Isolate the live server on a fresh database file, so the
        # seeded counts are exactly the displayed counts. The shared
        # process-wide DATA_ROOT is restored in tearDown.
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_db = portal.DB
        self._orig_ready = portal._SCHEMA_READY
        portal.DB = Path(self.tmp.name) / 'portal.sqlite3'
        portal._SCHEMA_READY = False
        scoreboard.reset_cache()
        self.addCleanup(self._restore_db)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), portal.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.port = self.server.server_address[1]

    def _restore_db(self):
        import portal
        portal.DB = self._orig_db
        portal._SCHEMA_READY = self._orig_ready
        scoreboard.reset_cache()
        self.tmp.cleanup()

    def request(self, method, path, body=b'', content_type=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
        try:
            headers = {}
            if content_type:
                headers['Content-Type'] = content_type
            conn.request(method, path, body=body, headers=headers)
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()

    def get(self, path):
        status, body = self.request('GET', path)
        return status, body.decode('utf-8', 'replace')

    def post_form(self, path, fields):
        body = urllib.parse.urlencode(fields).encode()
        return self.request('POST', path, body=body,
                            content_type='application/x-www-form-urlencoded')

    def test_scoreboard_journey(self):
        # Fresh database: no usage yet, so no scoreboard section.
        status, body = self.get('/')
        self.assertEqual(status, 200)
        self.assertNotIn('v8-scoreboard', body)
        # Seed known events; the page shows exactly those counts.
        with self.portal.db() as c:
            _seed(c, SEEDED)
        scoreboard.reset_cache()
        status, body = self.get('/')
        self.assertEqual(status, 200)
        self.assertIn('v8-scoreboard', body)
        self.assertIn('<strong>3</strong><span>demos run</span>', body)
        self.assertIn('<strong>4</strong><span>reports generated</span>', body)
        self.assertIn('<strong>33</strong><span>rows checked</span>', body)
        self.assertIn('<strong>9</strong><span>problem rows flagged</span>', body)
        self.assertIn('<strong>$3,150</strong><span>in sales checked</span>', body)
        # A real demo run moves every number (sample: 6 accepted,
        # 3 flagged, $800.00 paid revenue).
        status, _ = self.post_form('/try-sample', {'sample': '1'})
        self.assertEqual(status, 200)
        scoreboard.reset_cache()
        status, body = self.get('/')
        self.assertEqual(status, 200)
        self.assertIn('<strong>4</strong><span>demos run</span>', body)
        self.assertIn('<strong>5</strong><span>reports generated</span>', body)
        self.assertIn('<strong>42</strong><span>rows checked</span>', body)
        self.assertIn('<strong>12</strong><span>problem rows flagged</span>', body)
        self.assertIn('<strong>$3,950</strong><span>in sales checked</span>', body)


if __name__ == '__main__':
    unittest.main()
