"""Tests for the PRO offer on the saved-report page: a free user viewing a
report sees the offer at the moment of value — how many of the 1 free
reports they have used, how many are left, and the real BTCPay checkout
(or the manual-arrangement text when checkout is off). A PRO user sees
no upsell on their report page.
Run with:
  python -m unittest test_report_pro_offer -v
"""
import http.client
import os
import re
import tempfile
import threading
import time
import unittest
import urllib.parse
from http.server import ThreadingHTTPServer
from unittest.mock import patch

# The data dir must outlive the portal import: portal reads
# VELXTRIA_DATA_DIR once at module level, so a per-test temp dir would be
# deleted while later tests still use it.
_TMP = None
_ENV = None

# Module-level counter so every test gets a fresh user (a fresh 3-report
# quota); a per-test counter would re-register the same email and hit 409.
_USER_N = [0]
# messy (duplicate order, bad date, zero quantity), $800.00 paid revenue.
TEST_CSV = b"""Order ID,Order Date,Customer,Product,Quantity,Unit Price,Status,Region
T-001,2026-10-02,Test Customer A,Window Cleaning,2,85.00,Paid,Louisville
T-002,2026-10-05,Test Customer B,Deep Cleaning,1,180.00,Paid,Louisville
T-003,2026-10-09,Test Customer A,Gutter Cleaning,1,120.00,Paid,Jeffersonville
T-004,2026-10-15,Test Customer C,Window Cleaning,3,85.00,Pending,Louisville
T-005,2026-11-01,Test Customer B,Deep Cleaning,1,180.00,Paid,Louisville
T-006,2026-11-08,Test Customer D,Pressure Washing,1,150.00,Paid,New Albany
T-001,2026-11-10,Test Customer E,Window Cleaning,1,85.00,Paid,Louisville
T-007,not-a-date,Test Customer F,Deep Cleaning,1,180.00,Paid,Louisville
T-008,2026-11-12,Test Customer G,Gutter Cleaning,0,120.00,Paid,Louisville
"""


def setUpModule():
    global _TMP, _ENV
    _TMP = tempfile.TemporaryDirectory()
    _ENV = patch.dict(os.environ, {
        'VELXTRIA_DATA_DIR': _TMP.name,
        'VELXTRIA_DEPLOYMENT_MODE': 'local',
        # Dummy BTCPay config so checkout_enabled() is True and the report
        # page shows the real checkout form (same as test_paywall_analytics).
        'VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT': '1',
        'VELXTRIA_BTCPAY_MAINNET_URL': 'https://btcpay.example.com',
        'VELXTRIA_BTCPAY_MAINNET_STORE_ID': 'store123',
        'VELXTRIA_BTCPAY_MAINNET_API_KEY': 'key123',
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
    with portal.db() as c:
        c.execute(
            'DELETE FROM referral_rewards WHERE referrer_id IN '
            "(SELECT id FROM users WHERE email LIKE 'rpo%@example.test')")
        c.execute(
            'DELETE FROM referral_signups WHERE referrer_id IN '
            "(SELECT id FROM users WHERE email LIKE 'rpo%@example.test')")
        c.execute(
            "DELETE FROM referrals WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE 'rpo%@example.test')")
        c.execute(
            'DELETE FROM subscriptions WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'rpo%@example.test')")
        c.execute(
            'DELETE FROM report_write_journal WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'rpo%@example.test')")
        c.execute(
            'DELETE FROM reports WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'rpo%@example.test')")
        c.execute(
            'DELETE FROM sessions WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'rpo%@example.test')")
        c.execute("DELETE FROM users WHERE email LIKE 'rpo%@example.test'")
    _ENV.stop()
    _TMP.cleanup()
    # Leave DATA_ROOT in place: later modules reuse the same imported
    # portal, and a deleted data dir breaks their DB access.
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class ReportProOfferTests(unittest.TestCase):
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

    def get(self, path, cookie=None):
        headers = {'Cookie': 'velxtria_session=' + cookie} if cookie else None
        status, headers_out, body = self.request('GET', path, headers=headers)
        return status, headers_out, body.decode('utf-8', 'replace')

    def post_form(self, path, fields, cookie=None):
        body = urllib.parse.urlencode(fields).encode()
        headers = {'Cookie': 'velxtria_session=' + cookie} if cookie else None
        return self.request('POST', path, body=body,
                            content_type='application/x-www-form-urlencoded',
                            headers=headers)

    def user_id(self, email):
        with self.portal.db() as c:
            return c.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()[0]

    def csrf_for(self, email):
        with self.portal.db() as c:
            row = c.execute(
                'SELECT s.csrf FROM sessions s JOIN users u ON u.id=s.user_id '
                'WHERE u.email=? ORDER BY s.expires DESC LIMIT 1',
                (email,)).fetchone()
            return row[0]

    def sign_in(self, email):
        # /register signs the new account in at once, so the register
        # response already carries the session cookie; a second /login
        # would create a second session and the CSRF lookup by email
        # could return the wrong one.
        data = {'email': email, 'password': 'TestPass123456!'}
        status, headers, _ = self.post_form('/register', data)
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/')
        match = re.search(r'velxtria_session=([^;]+)', headers.get('Set-Cookie', ''))
        self.assertTrue(match, 'register did not set a session cookie')
        return match.group(1)

    def upload(self, cookie, csrf, filename='test-messy-sales.csv'):
        boundary = '----testboundary1234'
        parts = [
            ('--' + boundary + '\r\n'
             'Content-Disposition: form-data; name="csrf"\r\n\r\n'
             + csrf + '\r\n').encode(),
            ('--' + boundary + '\r\n'
             'Content-Disposition: form-data; name="file"; '
             'filename="' + filename + '"\r\n'
             'Content-Type: text/csv\r\n\r\n').encode(),
            TEST_CSV,
            ('\r\n--' + boundary + '--\r\n').encode(),
        ]
        return self.request('POST', '/upload', body=b''.join(parts),
                            content_type='multipart/form-data; boundary=' + boundary,
                            headers={'Cookie': 'velxtria_session=' + cookie})

    def make_user_and_upload(self):
        """A fresh user (fresh 3-report quota) with one real report."""
        _USER_N[0] += 1
        email = 'rpo%d@example.test' % _USER_N[0]
        cookie = self.sign_in(email)
        csrf = self.csrf_for(email)
        status, headers, _ = self.upload(cookie, csrf)
        self.assertEqual(status, 303)
        location = headers.get('Location', '')
        self.assertTrue(location.startswith('/report?id='),
                        'upload did not land on the report view: %s' % location)
        report_id = urllib.parse.parse_qs(
            urllib.parse.urlsplit(location).query)['id'][0]
        return email, cookie, report_id

    def make_pro(self, email, days_left=30):
        """Grant the user a verified PRO period covering now."""
        import subscriptions
        uid = self.user_id(email)
        now = int(time.time())
        with self.portal.db() as c:
            subscriptions.setup(c)
            c.execute(
                'INSERT INTO subscriptions'
                '(user_id,product_key,pricing_plan,status,source_reference,'
                'period_start,period_end,verified_at,verification_source,updated_at)'
                ' VALUES (?,?,?,?,?,?,?,?,?,?)',
                (uid, subscriptions.PRODUCT_KEY, subscriptions.PRICING_PLAN,
                 'active', 'inv1', now - 100, now + days_left * 86400,
                 now, 'btcpay_mainnet_verified', now))

    def test_free_report_page_offers_pro_checkout(self):
        email, cookie, report_id = self.make_user_and_upload()
        status, _, body = self.get('/report?id=' + report_id, cookie)
        self.assertEqual(status, 200)
        # The moment-of-value line: which free report this was, and how
        # many are left.
        self.assertIn('Free report 1 of 1 used', body)
        self.assertIn('You have 0 free reports left', body)
        # The real BTCPay checkout form, not a dead link.
        self.assertIn('VELXTRIA PRO', body)
        self.assertIn('action="/btcpay/mainnet/checkout"', body)

    def test_free_report_page_shows_manual_text_when_checkout_disabled(self):
        email, cookie, report_id = self.make_user_and_upload()
        with patch.dict(os.environ, {'VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT': '0'}):
            status, _, body = self.get('/report?id=' + report_id, cookie)
        self.assertEqual(status, 200)
        self.assertIn('Free report 1 of 1 used', body)
        self.assertNotIn('action="/btcpay/mainnet/checkout"', body)
        self.assertIn('manual arrangement', body)

    def test_second_upload_hits_paywall(self):
        # With a 1-report free tier there is no second free report: the
        # next upload after the first one shows the paywall, not a
        # second report page.
        email, cookie, report_id = self.make_user_and_upload()
        csrf = self.csrf_for(email)
        status, _, body = self.upload(cookie, csrf, filename='second.csv')
        self.assertEqual(status, 429)
        body = body.decode('utf-8', 'replace')
        self.assertIn('You have used your free report', body)
        self.assertIn('Pay $49 with Bitcoin', body)

    def test_pro_user_report_page_has_no_upsell(self):
        email, cookie, report_id = self.make_user_and_upload()
        self.make_pro(email)
        status, _, body = self.get('/report?id=' + report_id, cookie)
        self.assertEqual(status, 200)
        # The report itself still renders.
        self.assertIn('Report:', body)
        # But no PRO upsell of any kind.
        self.assertNotIn('Free report', body)
        self.assertNotIn('VELXTRIA PRO', body)
        self.assertNotIn('action="/btcpay/mainnet/checkout"', body)
