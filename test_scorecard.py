"""Tests for the shareable demo scorecard: % clean, problems found, top
issue types, paid revenue — on the demo result page (anonymous and
signed-in) and on the public share page, summaries only, 30-day expiry,
with a "try it with your own CSV" call to action. Run with:
  python -m unittest test_scorecard -v
"""
import http.client
import os
import re
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.parse
import uuid
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import demo_shares

_TMP = None
_ENV = None

PASSWORD = 'Scorecard123456!'

TEST_CSV = (
    b'Order ID,Order Date,Customer,Product,Quantity,Unit Price,Status,Region\n'
    b'X-001,2026-10-03,Secret Customer,Window Cleaning,2,85.00,Paid,Louisville\n'
    b'X-002,2026-10-05,Secret Customer,Deep Cleaning,1,180.00,Paid,Louisville\n'
    b'X-003,not-a-date,Secret Customer,Gutter Cleaning,1,120.00,Paid,Louisville\n'
)

REJECTED_HEADER = ['Source Line', 'Order ID', 'Order Date', 'Customer',
                   'Product', 'Quantity', 'Unit Price', 'Status', 'Region',
                   'Issue(s)']

SAMPLE_REPORT = {
    'monthly_rows': [['Month', 'Revenue'], ['2026-10', '350.00']],
    'product_rows': [['Product', 'Revenue'], ['Window Cleaning', '170.00']],
    'stats': ['Paid revenue (accepted Paid orders only): $350.00'],
    'accepted': 2, 'rejected': 1,
    'rejected_rows': [REJECTED_HEADER,
                      ['4', 'X-003', 'not-a-date', 'Secret Customer',
                       'Gutter Cleaning', '1', '120.00', 'Paid',
                       'Louisville', 'invalid date']],
}


def fresh_email():
    return 'scorecard-%s@example.com' % uuid.uuid4().hex[:12]


class ScorecardUnitTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        demo_shares.setup(self.conn)

    def test_scorecard_math(self):
        card = demo_shares.scorecard(SAMPLE_REPORT)
        self.assertEqual(card['clean_pct'], 67)
        self.assertEqual(card['problems'], 1)
        self.assertEqual(card['top_issues'], [['invalid date', 1]])
        self.assertEqual(card['paid'], '$350.00')

    def test_scorecard_all_clean(self):
        report = dict(SAMPLE_REPORT, accepted=5, rejected=0,
                      rejected_rows=[REJECTED_HEADER],
                      stats=['Paid revenue (accepted Paid orders only): $500.00'])
        card = demo_shares.scorecard(report)
        self.assertEqual(card['clean_pct'], 100)
        self.assertEqual(card['problems'], 0)
        self.assertEqual(card['top_issues'], [])
        self.assertEqual(card['paid'], '$500.00')

    def test_scorecard_top_three_issues(self):
        rows = [REJECTED_HEADER]
        issues = (['duplicate order ID'] * 3 + ['invalid date'] * 2
                  + ['quantity must be a positive integer']
                  + ['missing customer'])
        for i, issue in enumerate(issues):
            rows.append(['%d' % (i + 2), 'X-%03d' % i, '2026-10-03',
                         'Secret Customer', 'Window Cleaning', '1', '85.00',
                         'Paid', 'Louisville', issue])
        report = dict(SAMPLE_REPORT, accepted=2, rejected=len(issues),
                      rejected_rows=rows)
        card = demo_shares.scorecard(report)
        self.assertEqual(card['top_issues'],
                         [['duplicate order ID', 3],
                          ['invalid date', 2],
                          ['missing customer', 1]])

    def test_create_and_get_round_trip_keeps_scorecard(self):
        token = demo_shares.create(self.conn, SAMPLE_REPORT)
        shared = demo_shares.get(self.conn, token)
        self.assertIsNotNone(shared)
        self.assertEqual(shared['scorecard']['clean_pct'], 67)
        self.assertEqual(shared['scorecard']['problems'], 1)
        self.assertEqual(shared['scorecard']['top_issues'],
                         [['invalid date', 1]])
        self.assertEqual(shared['scorecard']['paid'], '$350.00')

    def test_legacy_row_without_top_issues_still_scores(self):
        # A share created before the scorecard has an empty top_issues
        # column; the percentage, problem count and paid revenue are
        # still derivable from the stored summaries.
        token = demo_shares.create(self.conn, SAMPLE_REPORT)
        self.conn.execute(
            "UPDATE demo_shares SET top_issues='' WHERE token=?", (token,))
        shared = demo_shares.get(self.conn, token)
        self.assertEqual(shared['scorecard']['clean_pct'], 67)
        self.assertEqual(shared['scorecard']['problems'], 1)
        self.assertEqual(shared['scorecard']['top_issues'], [])
        self.assertEqual(shared['scorecard']['paid'], '$350.00')

    def test_expired_share_returns_none_and_is_dropped(self):
        token = demo_shares.create(self.conn, SAMPLE_REPORT)
        self.conn.execute('UPDATE demo_shares SET expires=? WHERE token=?',
                          (int(time.time()) - 1, token))
        self.assertIsNone(demo_shares.get(self.conn, token))
        self.assertIsNone(self.conn.execute(
            'SELECT 1 FROM demo_shares WHERE token=?', (token,)).fetchone())


def setUpModule():
    global _TMP, _ENV
    _TMP = tempfile.TemporaryDirectory()
    _ENV = patch.dict(os.environ, {
        'VELXTRIA_DATA_DIR': _TMP.name,
        'VELXTRIA_DEPLOYMENT_MODE': 'local',
        'VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT': '0',
    })
    _ENV.start()
    import portal  # noqa: F401
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


def tearDownModule():
    _ENV.stop()
    _TMP.cleanup()
    import portal
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class ScorecardFlowTests(unittest.TestCase):
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
        status, headers, body = self.request('GET', path, headers=headers)
        return status, headers, body.decode('utf-8', 'replace')

    def post_form(self, path, fields, headers=None):
        body = urllib.parse.urlencode(fields).encode()
        return self.request('POST', path, body=body,
                            content_type='application/x-www-form-urlencoded',
                            headers=headers)

    def post_multipart(self, path, filename, data, headers=None):
        boundary = '----testboundary1234'
        head = ('--' + boundary + '\r\n'
                'Content-Disposition: form-data; name="file"; filename="%s"\r\n'
                'Content-Type: text/csv\r\n\r\n' % filename).encode()
        tail = ('\r\n--' + boundary + '--\r\n').encode()
        return self.request('POST', path, body=head + data + tail,
                            content_type='multipart/form-data; boundary=' + boundary,
                            headers=headers)

    def run_own_demo(self, headers=None):
        status, _, body = self.post_multipart('/try', 'sales.csv', TEST_CSV,
                                              headers=headers)
        self.assertEqual(status, 200)
        return body.decode('utf-8', 'replace')

    def run_sample_demo(self, headers=None):
        status, _, body = self.post_form('/try-sample', {'sample': '1'},
                                         headers=headers)
        self.assertEqual(status, 200)
        return body.decode('utf-8', 'replace')

    def signed_in_headers(self):
        email = fresh_email()
        status, _, _ = self.post_form('/register', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        status, headers, _ = self.post_form('/login', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        session = [p for p in headers['Set-Cookie'].split(',')
                   if 'velxtria_session=' in p][0].split(';')[0]
        return {'Cookie': session}

    def share_token_from(self, body):
        match = re.search(r'/demo/(?!signup|email)([A-Za-z0-9_-]+)', body)
        self.assertTrue(match, 'demo result page has no share link')
        return match.group(1)

    def test_own_demo_result_has_scorecard(self):
        body = self.run_own_demo()
        self.assertIn('Your data scorecard', body)
        self.assertIn('67% clean', body)
        self.assertIn('1 problem found', body)
        self.assertIn('invalid date', body)
        self.assertIn('$350.00', body)
        # Copy-link input carries the share URL.
        self.assertRegex(body, r'<input readonly value="[^"]*/demo/[A-Za-z0-9_-]+"')

    def test_sample_demo_result_has_scorecard(self):
        body = self.run_sample_demo()
        self.assertIn('Your data scorecard', body)
        self.assertIn('67% clean', body)
        self.assertIn('3 problems found', body)
        self.assertIn('duplicate order ID', body)
        self.assertIn('invalid date', body)
        self.assertIn('quantity must be a positive integer', body)
        self.assertIn('$800.00', body)

    def test_signed_in_demo_result_has_scorecard(self):
        headers = self.signed_in_headers()
        body = self.run_own_demo(headers=headers)
        self.assertIn('Your data scorecard', body)
        self.assertIn('67% clean', body)
        self.assertIn('1 problem found', body)
        self.assertIn('invalid date', body)

    def test_shared_page_shows_scorecard_and_cta(self):
        body = self.run_own_demo()
        token = self.share_token_from(body)
        status, _, shared = self.get('/demo/' + token)
        self.assertEqual(status, 200)
        self.assertIn('Your data scorecard', shared)
        self.assertIn('67% clean', shared)
        self.assertIn('1 problem found', shared)
        self.assertIn('$350.00', shared)
        self.assertIn('Try it with your own CSV', shared)
        self.assertIn('/#try', shared)
        # Raw row values never appear: no order ids, no customer names.
        self.assertNotIn('X-001', shared)
        self.assertNotIn('Secret Customer', shared)
        # Issue text is diagnostic detail: it stays on the owner's own
        # result page and never appears on the public share page.
        self.assertNotIn('invalid date', shared)
        self.assertNotIn('duplicate order ID', shared)

    def test_shared_page_expired_404(self):
        body = self.run_own_demo()
        token = self.share_token_from(body)
        db_path = self.portal.DATA_ROOT / 'portal.sqlite3'
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute('UPDATE demo_shares SET expires=? WHERE token=?',
                         (int(time.time()) - 1, token))
            conn.commit()
        finally:
            conn.close()
        status, _, _ = self.get('/demo/' + token)
        self.assertEqual(status, 404)


if __name__ == '__main__':
    unittest.main()
