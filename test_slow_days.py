"""Tests for the slow-day filler: spot the business's slowest weekday
and fill it with recent customers.

The filler is only ever computed from the business's own ledger — the
slowest weekday in the last 28 days, the next time it comes around,
and recent customers (7–30 days since their last order) to nudge into
it. With fewer than 10 paid orders in the window there is no pattern
to call, so nothing is shown; quiet customers belong to win-back,
not here.

Run with:
  python -m unittest test_slow_days -v
"""
import http.client
import os
import re
import tempfile
import threading
import unittest
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from unittest.mock import patch

_TMP = None
_ENV = None

PASSWORD = 'SlowDays123456!'

_EMAIL_N = [0]


def fresh_email():
    _EMAIL_N[0] += 1
    return 'slow-days-%d@example.com' % _EMAIL_N[0]


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
    _ENV.stop()
    _TMP.cleanup()
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


# Fixed "now": Tuesday Nov 24, 2026, 12:00 UTC. The 28-day window
# starts Oct 27; the nudge band is Oct 25 – Nov 17.
NOW = int(datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc).timestamp())


def sale(order_id, order_date, customer, product, quantity, unit_price,
         status='Paid'):
    return {'order_id': order_id, 'order_date': order_date,
            'customer': customer, 'product': product,
            'quantity': str(quantity), 'unit_price': unit_price,
            'status': status, 'region': 'Louisville'}


class SlowDaysTests(unittest.TestCase):
    def setUp(self):
        import portal
        self.portal = portal
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), portal.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.port = self.server.server_address[1]

    def request(self, method, path, body=b'', content_type=None,
                headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
        try:
            all_headers = dict(headers or {})
            if content_type:
                all_headers['Content-Type'] = content_type
            conn.request(method, path, body=body, headers=all_headers)
            resp = conn.getresponse()
            return (resp.status, dict(resp.headers), resp.read())
        finally:
            conn.close()

    def get(self, path, headers=None):
        status, headers_out, body = self.request('GET', path, headers=headers)
        return status, headers_out, body.decode('utf-8', 'replace')

    def post_form(self, path, fields, headers=None):
        body = urllib.parse.urlencode(fields).encode()
        return self.request('POST', path, body=body,
                            content_type='application/x-www-form-urlencoded',
                            headers=headers)

    def signed_in(self):
        email = fresh_email()
        status, _, _ = self.post_form('/register', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        status, headers, _ = self.post_form('/login', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        session = [p for p in headers['Set-Cookie'].split(',')
                   if 'velxtria_session=' in p][0].split(';')[0]
        headers = {'Cookie': session}
        with self.portal.db() as c:
            uid = c.execute(
                'SELECT id FROM users WHERE email=?', (email,)).fetchone()[0]
        return email, uid, headers

    def add_sale(self, uid, entry):
        import ledger
        with self.portal.db() as c:
            ledger.add_entry(c, uid, entry['order_id'],
                             entry['order_date'], entry['customer'],
                             entry['product'], entry['quantity'],
                             entry['unit_price'], entry['status'],
                             entry['region'])

    def seed_pattern(self, uid):
        """17 paid orders in the window, on every weekday except
        Thursday — so Thursday is the slowest with 0. Candidates, most
        recent first: Bob (Nov 17), Eve (Nov 14), Dan (Nov 10); Ann
        (Nov 23), Cid (Nov 18) and Fay (Nov 22) are too recent."""
        plan = [
            ('P-01', '2026-11-02', 'Ann', 'Deep Cleaning'),
            ('P-02', '2026-11-09', 'Ann', 'Deep Cleaning'),
            ('P-03', '2026-11-16', 'Ann', 'Deep Cleaning'),
            ('P-04', '2026-11-23', 'Ann', 'Deep Cleaning'),
            ('P-05', '2026-11-03', 'Bob', 'Gutter Cleaning'),
            ('P-06', '2026-11-10', 'Bob', 'Gutter Cleaning'),
            ('P-07', '2026-11-17', 'Bob', 'Gutter Cleaning'),
            ('P-08', '2026-11-04', 'Cid', 'Window Cleaning'),
            ('P-09', '2026-11-11', 'Cid', 'Window Cleaning'),
            ('P-10', '2026-11-18', 'Cid', 'Window Cleaning'),
            ('P-11', '2026-11-06', 'Dan', 'Deep Cleaning'),
            ('P-12', '2026-11-10', 'Dan', 'Deep Cleaning'),
            ('P-13', '2026-11-07', 'Eve', 'Gutter Cleaning'),
            ('P-14', '2026-11-14', 'Eve', 'Gutter Cleaning'),
            ('P-15', '2026-11-08', 'Fay', 'Window Cleaning'),
            ('P-16', '2026-11-15', 'Fay', 'Window Cleaning'),
            ('P-17', '2026-11-22', 'Fay', 'Window Cleaning'),
        ]
        for oid, day, customer, product in plan:
            self.add_sale(uid, sale(oid, day, customer, product, 1, '90.00'))

    def test_finds_slowest_weekday_and_candidates(self):
        import slow_days
        _, uid, _ = self.signed_in()
        self.seed_pattern(uid)
        with self.portal.db() as c:
            found = slow_days.filler(c, uid, now=NOW)
        self.assertIsNotNone(found)
        self.assertEqual(found['weekday'], 'Thursday')
        self.assertEqual(found['next_date'], '2026-11-26')
        self.assertEqual(found['next_label'], 'Thu Nov 26')
        self.assertEqual(found['orders'], 0)
        self.assertEqual(
            [c['customer'] for c in found['candidates']],
            ['Bob', 'Eve', 'Dan'])

    def test_draft_text_is_personal(self):
        import slow_days
        _, uid, _ = self.signed_in()
        self.seed_pattern(uid)
        with self.portal.db() as c:
            found = slow_days.filler(c, uid, now=NOW)
        bob = found['candidates'][0]
        self.assertEqual(bob['customer'], 'Bob')
        self.assertIn('Thu Nov 26', bob['text'])
        self.assertIn('Tue Nov 17', bob['text'])
        self.assertIn('Gutter Cleaning', bob['text'])
        self.assertNotIn('discount', bob['text'].lower())

    def test_too_few_orders_shows_nothing(self):
        import slow_days
        _, uid, _ = self.signed_in()
        self.add_sale(uid, sale('F-001', '2026-11-23', 'Ann',
                                'Deep Cleaning', 4, '90.00'))
        self.add_sale(uid, sale('F-002', '2026-11-24', 'Bob',
                                'Gutter Cleaning', 1, '120.00'))
        with self.portal.db() as c:
            self.assertIsNone(slow_days.filler(c, uid, now=NOW))

    def test_no_candidates_shows_nothing(self):
        import slow_days
        _, uid, _ = self.signed_in()
        # 10+ orders, all in the last 7 days: a slowest weekday exists
        # but nobody is in the nudge band.
        for i, day in enumerate(['2026-11-18', '2026-11-19',
                                 '2026-11-20', '2026-11-21',
                                 '2026-11-22', '2026-11-23',
                                 '2026-11-24']):
            self.add_sale(uid, sale('N-%02d' % i, day, 'Ann',
                                    'Deep Cleaning', 1, '90.00'))
            self.add_sale(uid, sale('N-1%d' % i, day, 'Bob',
                                    'Gutter Cleaning', 1, '90.00'))
        with self.portal.db() as c:
            self.assertIsNone(slow_days.filler(c, uid, now=NOW))

    def test_dashboard_shows_slow_day_filler(self):
        # Dates relative to the real current week, so this holds on any
        # day the suite runs: orders on the last 14 days except
        # Thursdays, with two customers in the nudge band.
        today = datetime.now(timezone.utc).date()
        _, uid, headers = self.signed_in()
        n = 0
        for back in range(1, 15):
            day = today - timedelta(days=back)
            if day.weekday() == 3:
                continue
            n += 1
            self.add_sale(uid, sale(
                'D-%02d' % n, day.isoformat(),
                'Ann' if n % 2 else 'Bob', 'Deep Cleaning', 1, '90.00'))
        self.add_sale(uid, sale('D-90', (today - timedelta(days=10)
                                         ).isoformat(), 'Dan',
                                'Gutter Cleaning', 1, '90.00'))
        self.add_sale(uid, sale('D-91', (today - timedelta(days=12)
                                         ).isoformat(), 'Eve',
                                'Window Cleaning', 1, '90.00'))
        _, _, text = self.get('/', headers=headers)
        self.assertIn('Fill your slow days', text)
        self.assertIn('Thursday', text)
        self.assertIn('open slot', text)
        self.assertIn('Dan', text)

    def test_slow_days_sql_is_postgres_portable(self):
        # The filler only reads the ledger with plain SELECTs — keep
        # SQLite-only statements out of this module too.
        import slow_days
        import pathlib
        src = pathlib.Path(slow_days.__file__).read_text()
        self.assertNotIn('OR IGNORE', src)
        self.assertNotIn('OR REPLACE', src)


if __name__ == '__main__':
    unittest.main()
