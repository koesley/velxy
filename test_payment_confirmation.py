"""Tests for the payment confirmation flow: after paying on BTCPay the
payer returns to /account?paid=1, which re-verifies against BTCPay and
shows a confirmation only for the verified state — PRO active once the
payment settled, still-confirming while it is pending, a retry note when
verification is unavailable, and nothing at all when there is no order
(the ?paid=1 parameter alone is never proof of payment).
Run with:
  python -m unittest test_payment_confirmation -v
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

_TMP = None
_ENV = None

_USER_N = [0]

MAINNET_ENV = {
    'VELXTRIA_BTCPAY_MAINNET_URL': 'https://btcpay.example.com',
    'VELXTRIA_BTCPAY_MAINNET_STORE_ID': 'store123',
    'VELXTRIA_BTCPAY_MAINNET_API_KEY': 'api-key-123',
    'VELXTRIA_BTCPAY_MAINNET_WEBHOOK_SECRET': 'whsec-123',
    'VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT': '1',
}


def setUpModule():
    global _TMP, _ENV
    _TMP = tempfile.TemporaryDirectory()
    _ENV = patch.dict(os.environ, {
        'VELXTRIA_DATA_DIR': _TMP.name,
        'VELXTRIA_DEPLOYMENT_MODE': 'local',
    })
    _ENV.start()
    import portal  # noqa: F401
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


def tearDownModule():
    import portal
    with portal.db() as c:
        c.execute(
            'DELETE FROM reports WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'pc%@example.test')")
        c.execute(
            'DELETE FROM sessions WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'pc%@example.test')")
        c.execute(
            "DELETE FROM btcpay_orders WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE 'pc%@example.test')")
        c.execute(
            'DELETE FROM subscriptions WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'pc%@example.test')")
        c.execute("DELETE FROM users WHERE email LIKE 'pc%@example.test'")
    _ENV.stop()
    _TMP.cleanup()
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class PaymentConfirmationTests(unittest.TestCase):
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

    def sign_in(self, email):
        data = {'email': email, 'password': 'TestPass123456!'}
        status, headers, _ = self.post_form('/register', data)
        self.assertEqual(status, 303)
        status, headers, _ = self.post_form('/login', data)
        self.assertEqual(status, 303)
        match = re.search(r'velxtria_session=([^;]+)', headers.get('Set-Cookie', ''))
        self.assertTrue(match, 'login did not set a session cookie')
        return match.group(1)

    def new_user(self):
        _USER_N[0] += 1
        email = 'pc%d@example.test' % _USER_N[0]
        return email, self.sign_in(email)

    def user_id(self, email):
        with self.portal.db() as c:
            return c.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()[0]

    def make_order(self, email, status, settled=False):
        import btcpay_mainnet  # noqa: F401  (ensures the orders table exists)
        now = int(time.time())
        with self.portal.db() as c:
            uid = self.user_id(email)
            c.execute(
                'INSERT INTO btcpay_orders'
                '(order_id,user_id,invoice_id,checkout_url,status,created_at,settled_at,network)'
                ' VALUES (?,?,?,?,?,?,?,?)',
                ('vx-' + email.split('@')[0], uid, 'inv-' + email.split('@')[0],
                 'https://btcpay.example.com/i/inv1', status, now,
                 now if settled else 0, 'mainnet'))
            return uid

    def make_pro(self, uid):
        import subscriptions
        now = int(time.time())
        with self.portal.db() as c:
            c.execute(
                'INSERT INTO subscriptions'
                '(user_id,product_key,pricing_plan,status,source_reference,'
                'period_start,period_end,verified_at,verification_source,updated_at)'
                ' VALUES (?,?,?,?,?,?,?,?,?,?)',
                (uid, subscriptions.PRODUCT_KEY, subscriptions.PRICING_PLAN,
                 'active', 'inv1', now - 100, now + 30 * 86400, now, 'test', now))

    def test_paid_settled_shows_pro_confirmation(self):
        email, cookie = self.new_user()
        uid = self.make_order(email, 'settled', settled=True)
        self.make_pro(uid)
        status, _, body = self.get('/account?paid=1', cookie)
        self.assertEqual(status, 200)
        self.assertIn('Payment received', body)
        self.assertIn('PRO is active', body)
        self.assertIn('Active through', body)

    def test_paid_pending_shows_confirming_not_active(self):
        email, cookie = self.new_user()
        self.make_order(email, 'pending')
        status, _, body = self.get('/account?paid=1', cookie)
        self.assertEqual(status, 200)
        self.assertIn('being confirmed', body)
        self.assertIn('Check payment status', body)
        self.assertNotIn('PRO is active', body)

    def test_paid_without_orders_shows_nothing(self):
        _, cookie = self.new_user()
        status, _, body = self.get('/account?paid=1', cookie)
        self.assertEqual(status, 200)
        self.assertNotIn('Payment received', body)
        self.assertNotIn('being confirmed', body)
        self.assertNotIn('Checking your payment', body)

    def test_account_without_paid_param_shows_no_banner(self):
        email, cookie = self.new_user()
        uid = self.make_order(email, 'settled', settled=True)
        self.make_pro(uid)
        status, _, body = self.get('/account', cookie)
        self.assertEqual(status, 200)
        self.assertNotIn('Payment received', body)

    def test_paid_verify_failure_shows_retry(self):
        email, cookie = self.new_user()
        self.make_order(email, 'pending')
        import portal
        with patch.dict(os.environ, MAINNET_ENV):
            with patch.object(portal.btcpay_mainnet, 'reconcile',
                              side_effect=RuntimeError('BTCPay unreachable')):
                status, _, body = self.get('/account?paid=1', cookie)
        self.assertEqual(status, 200)
        self.assertIn('could not reach BTCPay', body)
        self.assertNotIn('PRO is active', body)

    def test_paid_requires_login(self):
        status, headers, _ = self.get('/account?paid=1')
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/login')


if __name__ == '__main__':
    unittest.main()
