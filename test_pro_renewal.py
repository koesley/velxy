"""Tests for the PRO renewal engine: a PRO user whose period ends soon sees
a countdown and a one-click renew button on the dashboard and the account
page, and a renewal payment extends the period from when the current one
ends — renewing early never loses days. Run with:
  python -m unittest test_pro_renewal -v
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


def settled_invoice(invoice_id, order_id):
    return {
        'id': invoice_id, 'storeId': 'store123', 'amount': '49.00',
        'currency': 'USD', 'status': 'Settled',
        'metadata': {'orderId': order_id,
                     'itemDesc': 'VELXTRIA PRO - 30 Days - 50 Reports'},
        'checkoutLink': 'https://btcpay.example.com/i/' + invoice_id,
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
            'DELETE FROM referral_rewards WHERE referrer_id IN '
            "(SELECT id FROM users WHERE email LIKE 'pr%@example.test')")
        c.execute(
            'DELETE FROM referral_signups WHERE referrer_id IN '
            "(SELECT id FROM users WHERE email LIKE 'pr%@example.test')")
        c.execute(
            "DELETE FROM referrals WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE 'pr%@example.test')")
        c.execute(
            'DELETE FROM reports WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'pr%@example.test')")
        c.execute(
            'DELETE FROM sessions WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'pr%@example.test')")
        c.execute(
            "DELETE FROM btcpay_orders WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE 'pr%@example.test')")
        c.execute(
            'DELETE FROM subscriptions WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'pr%@example.test')")
        c.execute("DELETE FROM users WHERE email LIKE 'pr%@example.test'")
    _ENV.stop()
    _TMP.cleanup()
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class ProRenewalTests(unittest.TestCase):
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
        email = 'pr%d@example.test' % _USER_N[0]
        return email, self.sign_in(email)

    def user_id(self, email):
        with self.portal.db() as c:
            return c.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()[0]

    def csrf_for(self, email):
        with self.portal.db() as c:
            return c.execute(
                'SELECT csrf FROM sessions WHERE user_id=?',
                (self.user_id(email),)).fetchone()[0]

    def make_pro(self, email, days_left):
        import subscriptions
        now = int(time.time())
        uid = self.user_id(email)
        with self.portal.db() as c:
            c.execute(
                'INSERT INTO subscriptions'
                '(user_id,product_key,pricing_plan,status,source_reference,'
                'period_start,period_end,verified_at,verification_source,updated_at)'
                ' VALUES (?,?,?,?,?,?,?,?,?,?)',
                (uid, subscriptions.PRODUCT_KEY, subscriptions.PRICING_PLAN,
                 'active', 'inv1', now - 100, now + days_left * 86400,
                 now, 'test', now))
        return uid

    def test_dashboard_shows_renewal_inside_window(self):
        email, cookie = self.new_user()
        self.make_pro(email, 6)
        with patch.dict(os.environ, MAINNET_ENV):
            with patch.object(self.portal.btcpay_mainnet, 'reconcile',
                              return_value=False):
                status, _, body = self.get('/', cookie)
        self.assertEqual(status, 200)
        self.assertIn('Renew PRO', body)
        self.assertIn('in 6 days', body)
        self.assertIn('Renew PRO — $49 with Bitcoin', body)
        self.assertIn('action="/btcpay/mainnet/checkout"', body)

    def test_dashboard_hides_renewal_outside_window(self):
        email, cookie = self.new_user()
        self.make_pro(email, 25)
        with patch.dict(os.environ, MAINNET_ENV):
            with patch.object(self.portal.btcpay_mainnet, 'reconcile',
                              return_value=False):
                status, _, body = self.get('/', cookie)
        self.assertEqual(status, 200)
        self.assertNotIn('Renew PRO', body)

    def test_dashboard_renewal_tomorrow(self):
        email, cookie = self.new_user()
        self.make_pro(email, 1)
        with patch.dict(os.environ, MAINNET_ENV):
            with patch.object(self.portal.btcpay_mainnet, 'reconcile',
                              return_value=False):
                status, _, body = self.get('/', cookie)
        self.assertEqual(status, 200)
        self.assertIn('tomorrow', body)

    def test_account_shows_renewal(self):
        email, cookie = self.new_user()
        self.make_pro(email, 6)
        with patch.dict(os.environ, MAINNET_ENV):
            status, _, body = self.get('/account', cookie)
        self.assertEqual(status, 200)
        self.assertIn('Renew PRO', body)
        self.assertIn('in 6 days', body)

    def test_expired_pro_gets_upgrade_not_renewal(self):
        email, cookie = self.new_user()
        self.make_pro(email, -1)
        with patch.dict(os.environ, MAINNET_ENV):
            with patch.object(self.portal.btcpay_mainnet, 'reconcile',
                              return_value=False):
                status, _, body = self.get('/', cookie)
        self.assertEqual(status, 200)
        self.assertNotIn('Renew PRO', body)
        self.assertIn('VELXTRIA PRO · $49 / 30 days', body)

    def test_renewal_checkout_allowed_for_pro(self):
        import btcpay_mainnet
        email, cookie = self.new_user()
        self.make_pro(email, 6)
        csrf = self.csrf_for(email)
        with patch.dict(os.environ, MAINNET_ENV):
            with patch.object(
                    self.portal.btcpay_mainnet, 'issue_invoice',
                    return_value=('inv-new',
                                  'https://btcpay.example.com/i/inv-new')):
                status, headers, _ = self.post_form(
                    '/btcpay/mainnet/checkout', {'csrf': csrf}, cookie)
        self.assertEqual(status, 303)
        self.assertTrue(headers.get('Location', '').startswith(
            'https://btcpay.example.com/i/'))
        with self.portal.db() as c:
            row = c.execute(
                "SELECT status FROM btcpay_orders WHERE user_id=? "
                "AND network='mainnet'",
                (self.user_id(email),)).fetchone()
        self.assertEqual(row[0], 'pending')

    def test_renewal_settlement_extends_from_period_end(self):
        import btcpay_mainnet
        import subscriptions
        email, cookie = self.new_user()
        uid = self.make_pro(email, 6)
        old_end = int(time.time()) + 6 * 86400

        def fake(method, path, payload=None):
            if method == 'GET' and path == '/invoices/inv1':
                return settled_invoice('inv1', order_id)
            raise RuntimeError('unexpected fake call %s %s' % (method, path))

        with patch.dict(os.environ, MAINNET_ENV):
            with self.portal.db() as c:
                order_id = btcpay_mainnet.create_order(c, uid)
                c.execute("UPDATE btcpay_orders SET invoice_id=?,checkout_url=?,"
                          "status='pending' WHERE order_id=?",
                          ('inv1', 'https://btcpay.example.com/i/inv1', order_id))
            with self.portal.db() as c:
                self.assertTrue(btcpay_mainnet.reconcile(c, uid, req=fake))
            with self.portal.db() as c:
                ent = subscriptions.entitlement(c, uid)
        self.assertEqual(ent['plan'], 'pro')
        self.assertEqual(ent['end'], old_end + 30 * 86400)
        # The period start stays put: PRO access is continuous, so a user
        # who renews early is never left without PRO until the old period
        # would have ended.
        self.assertLessEqual(ent['start'], int(time.time()))


if __name__ == '__main__':
    unittest.main()
