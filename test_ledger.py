"""Tests for the Sales Ledger: log sales one at a time, get a living report.

VELXTRIA used to be a one-shot tool — upload a CSV, get a report, leave.
Nothing gave a business a reason to come back the next day. The ledger
changes that: a signed-in user logs each sale as it happens, and the
dashboard shows a live monthly + product summary of everything logged so
far. The ledger can be downloaded as a clean CSV or turned into a full
report (which counts against the free allowance, the same as an upload).

Entries are validated on add with the report engine's own rules, so a
ledger can never hold a row the engine would flag, and the order ID must
be unique per user.

Run with:
  python -m unittest test_ledger -v
"""
import http.client
import io
import os
import re
import tempfile
import threading
import unittest
import urllib.parse
import zipfile
from http.server import ThreadingHTTPServer
from unittest.mock import patch

# The data dir must outlive the portal import: portal reads
# VELXTRIA_DATA_DIR once at module level, so a per-test temp dir would be
# deleted while later tests still use it.
_TMP = None
_ENV = None

PASSWORD = 'LedgerPass123456!'

# Module-level counter: the data dir (and its users table) is shared by
# every test in this module, so emails must be unique across tests, not
# just within one test.
_EMAIL_N = [0]


def fresh_email():
    _EMAIL_N[0] += 1
    return 'ledger-%d@example.com' % _EMAIL_N[0]


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
    # DATA_ROOT is fixed at first import, which may have happened in an
    # earlier test module whose temp dir is already deleted; recreate it so
    # sqlite can open the DB file again.
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


def tearDownModule():
    import portal
    _ENV.stop()
    _TMP.cleanup()
    # Leave DATA_ROOT in place: later modules reuse the same imported
    # portal, and a deleted data dir breaks their DB access.
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


SALE_1 = {'order_id': 'L-001', 'order_date': '2026-11-20',
          'customer': 'Ann', 'product': 'Window Cleaning',
          'quantity': '2', 'unit_price': '85.00', 'status': 'Paid',
          'region': 'Louisville'}
SALE_2 = {'order_id': 'L-002', 'order_date': '2026-11-21',
          'customer': 'Bob', 'product': 'Deep Cleaning',
          'quantity': '1', 'unit_price': '180.00', 'status': 'Paid',
          'region': 'Louisville'}
SALE_3 = {'order_id': 'L-003', 'order_date': '2026-11-22',
          'customer': 'Cid', 'product': 'Window Cleaning',
          'quantity': '1', 'unit_price': '85.00', 'status': 'Pending',
          'region': 'Louisville'}


class LedgerTests(unittest.TestCase):
    def setUp(self):
        import portal
        self.portal = portal
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), portal.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.port = self.server.server_address[1]

    def request(self, method, path, body=b'', content_type=None, headers=None):
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
        _, _, text = self.get('/', headers=headers)
        csrf = re.search(r'name="csrf" value="([^"]+)"', text).group(1)
        return headers, csrf

    def add_sale(self, headers, csrf, sale):
        fields = dict(sale)
        fields['csrf'] = csrf
        return self.post_form('/ledger/add', fields, headers=headers)

    def test_dashboard_shows_ledger_panel(self):
        headers, _ = self.signed_in()
        _, _, text = self.get('/', headers=headers)
        self.assertIn('Sales Ledger', text)
        self.assertIn('action="/ledger/add"', text)
        self.assertIn('Log this sale', text)
        self.assertIn('no CSV', text)

    def test_anonymous_cannot_use_ledger(self):
        status, _, _ = self.post_form('/ledger/add', dict(SALE_1))
        self.assertEqual(status, 401)
        # A GET to a protected page redirects to the sign-in page.
        status, _, _ = self.get('/ledger.csv')
        self.assertEqual(status, 303)
        status, _, _ = self.post_form('/ledger/report', {'csrf': 'x'})
        self.assertEqual(status, 401)

    def test_add_sale_and_live_summary(self):
        headers, csrf = self.signed_in()
        for sale in (SALE_1, SALE_2, SALE_3):
            status, _, _ = self.add_sale(headers, csrf, sale)
            self.assertEqual(status, 303, 'add %s failed' % sale['order_id'])
        _, _, text = self.get('/', headers=headers)
        self.assertIn('3 sales logged', text)
        # Paid only: L-001 ($170) + L-002 ($180) = $350 in Nov; L-003 is
        # Pending, so it does not count toward revenue.
        self.assertIn('350.00', text)
        self.assertIn('Window Cleaning', text)
        self.assertIn('170.00', text)
        self.assertIn('Generate a report from my ledger', text)
        self.assertIn('/ledger.csv', text)
        # The recent-entries table shows all three.
        self.assertIn('L-001', text)
        self.assertIn('L-002', text)
        self.assertIn('L-003', text)

    def test_add_sale_rejects_bad_data(self):
        headers, csrf = self.signed_in()
        cases = [
            (dict(SALE_1, order_id=''), 'missing order ID'),
            (dict(SALE_1, order_date='not-a-date'), 'invalid date'),
            (dict(SALE_1, quantity='0'),
             'quantity must be a positive integer'),
            (dict(SALE_1, quantity='two'),
             'quantity must be a positive integer'),
            (dict(SALE_1, unit_price='-5'), 'invalid unit price'),
            (dict(SALE_1, unit_price='free'), 'invalid unit price'),
            (dict(SALE_1, status='Maybe'), 'unknown status'),
            (dict(SALE_1, customer=''), 'missing customer'),
            (dict(SALE_1, product=''), 'missing product'),
            (dict(SALE_1, region=''), 'missing region'),
        ]
        for fields, message in cases:
            status, _, body = self.add_sale(headers, csrf, fields)
            self.assertEqual(status, 400, 'expected 400 for %r' % fields)
            self.assertIn(message, body.decode('utf-8', 'replace'))

    def test_duplicate_order_id_rejected(self):
        headers, csrf = self.signed_in()
        status, _, _ = self.add_sale(headers, csrf, SALE_1)
        self.assertEqual(status, 303)
        status, _, body = self.add_sale(
            headers, csrf, dict(SALE_1, order_date='2026-11-23'))
        self.assertEqual(status, 400)
        self.assertIn('already in your ledger', body.decode('utf-8', 'replace'))

    def test_download_ledger_csv(self):
        headers, csrf = self.signed_in()
        status, _, _ = self.get('/ledger.csv', headers=headers)
        self.assertEqual(status, 404, 'empty ledger should 404')
        for sale in (SALE_1, SALE_2):
            status, _, _ = self.add_sale(headers, csrf, sale)
            self.assertEqual(status, 303)
        status, _, text = self.get('/ledger.csv', headers=headers)
        self.assertEqual(status, 200)
        self.assertIn('Order ID,Order Date,Customer,Product,Quantity,'
                      'Unit Price,Status,Region', text)
        self.assertIn('L-001,2026-11-20,Ann,Window Cleaning,2,85.00,Paid,'
                      'Louisville', text)
        self.assertIn('L-002,2026-11-21,Bob,Deep Cleaning,1,180.00,Paid,'
                      'Louisville', text)

    def test_report_from_ledger(self):
        headers, csrf = self.signed_in()
        status, _, body = self.post_form('/ledger/report', {'csrf': csrf},
                                         headers=headers)
        self.assertEqual(status, 400, 'empty ledger should 400')
        for sale in (SALE_1, SALE_2, SALE_3):
            status, _, _ = self.add_sale(headers, csrf, sale)
            self.assertEqual(status, 303)
        status, resp_headers, _ = self.post_form(
            '/ledger/report', {'csrf': csrf}, headers=headers)
        self.assertEqual(status, 303)
        location = resp_headers.get('Location', '')
        self.assertTrue(location.startswith('/report?id='),
                        'expected a report redirect, got %r' % location)
        _, _, text = self.get(location, headers=headers)
        self.assertIn('350.00', text)
        self.assertIn('Accepted 3 rows', text)
        self.assertIn('flagged 0 rows', text)
        # The report counts against the free allowance (1 of 3 used).
        _, _, dash = self.get('/', headers=headers)
        self.assertIn('1', dash)

    def test_ledger_is_per_user(self):
        headers_a, csrf_a = self.signed_in()
        status, _, _ = self.add_sale(headers_a, csrf_a, SALE_1)
        self.assertEqual(status, 303)
        # A second user starts with an empty ledger and can reuse the
        # same order ID.
        headers_b, csrf_b = self.signed_in()
        _, _, text = self.get('/', headers=headers_b)
        self.assertIn('no CSV', text)
        self.assertNotIn('L-001', text)
        status, _, _ = self.add_sale(headers_b, csrf_b, SALE_1)
        self.assertEqual(status, 303)
