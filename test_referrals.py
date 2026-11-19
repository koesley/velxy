"""Tests for the referral program: codes, signup attribution, and the free
month of PRO credited when a referred user pays. Run with:
  python -m unittest test_referrals -v
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
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import referrals
import subscriptions

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


class ReferralUnitTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL)')
        self.conn.execute("INSERT INTO users(id,email) VALUES (1,'a@example.test')")
        self.conn.execute("INSERT INTO users(id,email) VALUES (2,'b@example.test')")
        referrals.setup(self.conn)
        subscriptions.setup(self.conn)

    def test_code_is_stable_and_unique(self):
        code = referrals.code_for(self.conn, 1)
        self.assertEqual(len(code), 8)
        self.assertTrue(all(ch in referrals.CODE_ALPHABET for ch in code))
        self.assertEqual(referrals.code_for(self.conn, 1), code)
        self.assertNotEqual(referrals.code_for(self.conn, 2), code)

    def test_invalid_codes_rejected(self):
        self.assertFalse(referrals.valid_code(''))
        self.assertFalse(referrals.valid_code('abc'))
        self.assertFalse(referrals.valid_code('ABCDEFGH'))
        self.assertFalse(referrals.valid_code(None))
        self.assertIsNone(referrals.referrer_for_code(self.conn, 'zzzzzzzz'))

    def test_record_signup(self):
        code = referrals.code_for(self.conn, 1)
        self.assertEqual(referrals.referrer_for_code(self.conn, code), 1)
        self.assertEqual(referrals.record_signup(self.conn, 2, code), 1)
        self.assertEqual(referrals.stats(self.conn, 1)['signups'], 1)
        self.assertIsNone(referrals.record_signup(self.conn, 2, 'zzzzzzzz'))
        referrals.record_signup(self.conn, 2, code)
        self.assertEqual(referrals.stats(self.conn, 1)['signups'], 1)

    def test_reward_requires_signup(self):
        self.assertFalse(referrals.reward_for_payment(self.conn, 2, 'vx-1'))

    def test_reward_credits_pro_once(self):
        code = referrals.code_for(self.conn, 1)
        referrals.record_signup(self.conn, 2, code)
        self.assertTrue(referrals.reward_for_payment(self.conn, 2, 'vx-1'))
        ent = subscriptions.entitlement(self.conn, 1)
        self.assertEqual(ent['plan'], 'pro')
        self.assertEqual(referrals.stats(self.conn, 1)['paid'], 1)
        end_first = ent['end']
        self.assertFalse(referrals.reward_for_payment(self.conn, 2, 'vx-2'))
        self.assertEqual(subscriptions.entitlement(self.conn, 1)['end'], end_first)

    def test_reward_extends_existing_pro(self):
        now = int(time.time())
        with self.conn:
            self.conn.execute(
                'INSERT INTO subscriptions'
                '(user_id,product_key,pricing_plan,status,source_reference,'
                'period_start,period_end,verified_at,verification_source,updated_at)'
                ' VALUES (?,?,?,?,?,?,?,?,?,?)',
                (1, subscriptions.PRODUCT_KEY, subscriptions.PRICING_PLAN,
                 'active', 'inv0', now - 100, now + 10 * 86400, now, 'test', now))
        code = referrals.code_for(self.conn, 1)
        referrals.record_signup(self.conn, 2, code)
        self.assertTrue(referrals.reward_for_payment(self.conn, 2, 'vx-1'))
        ent = subscriptions.entitlement(self.conn, 1)
        self.assertEqual(ent['start'], now - 100)
        self.assertEqual(ent['end'], now + 40 * 86400)


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
            "(SELECT id FROM users WHERE email LIKE 'rf%@example.test')")
        c.execute(
            'DELETE FROM referral_signups WHERE referrer_id IN '
            "(SELECT id FROM users WHERE email LIKE 'rf%@example.test')")
        c.execute(
            "DELETE FROM referrals WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE 'rf%@example.test')")
        c.execute(
            'DELETE FROM reports WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'rf%@example.test')")
        c.execute(
            'DELETE FROM sessions WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'rf%@example.test')")
        c.execute(
            "DELETE FROM btcpay_orders WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE 'rf%@example.test')")
        c.execute(
            'DELETE FROM subscriptions WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'rf%@example.test')")
        c.execute("DELETE FROM users WHERE email LIKE 'rf%@example.test'")
    _ENV.stop()
    _TMP.cleanup()
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class ReferralFlowTests(unittest.TestCase):
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

    def get(self, path, cookie=None, headers=None):
        all_headers = dict(headers or {})
        if cookie:
            all_headers['Cookie'] = cookie
        status, headers_out, body = self.request('GET', path, headers=all_headers)
        return status, headers_out, body.decode('utf-8', 'replace')

    def post_form(self, path, fields, cookie=None):
        body = urllib.parse.urlencode(fields).encode()
        headers = {'Cookie': cookie} if cookie else None
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
        email = 'rf%d@example.test' % _USER_N[0]
        return email, self.sign_in(email)

    def user_id(self, email):
        with self.portal.db() as c:
            return c.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()[0]

    def code_for(self, email):
        with self.portal.db() as c:
            return referrals.code_for(c, self.user_id(email))

    def test_landing_sets_referral_cookie(self):
        email, _ = self.new_user()
        code = self.code_for(email)
        status, headers, _ = self.get('/?ref=' + code)
        self.assertEqual(status, 200)
        self.assertIn('velxtria_ref=' + code, headers.get('Set-Cookie', ''))
        status, headers, _ = self.get('/?ref=zzzzzzzz')
        self.assertNotIn('velxtria_ref', headers.get('Set-Cookie', ''))
        status, headers, _ = self.get('/')
        self.assertNotIn('velxtria_ref', headers.get('Set-Cookie', ''))

    def test_register_with_cookie_attributes_signup(self):
        referrer, _ = self.new_user()
        code = self.code_for(referrer)
        _USER_N[0] += 1
        email = 'rf%d@example.test' % _USER_N[0]
        status, _, _ = self.post_form(
            '/register', {'email': email, 'password': 'TestPass123456!'},
            cookie='velxtria_ref=' + code)
        self.assertEqual(status, 303)
        with self.portal.db() as c:
            row = c.execute(
                'SELECT referrer_id FROM referral_signups WHERE user_id=?',
                (self.user_id(email),)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], self.user_id(referrer))

    def test_register_with_bad_ref_attributes_nothing(self):
        _USER_N[0] += 1
        email = 'rf%d@example.test' % _USER_N[0]
        status, _, _ = self.post_form(
            '/register', {'email': email, 'password': 'TestPass123456!'},
            cookie='velxtria_ref=zzzzzzzz')
        self.assertEqual(status, 303)
        with self.portal.db() as c:
            row = c.execute(
                'SELECT 1 FROM referral_signups WHERE user_id=?',
                (self.user_id(email),)).fetchone()
        self.assertIsNone(row)

    def test_register_form_carries_ref_field(self):
        referrer, _ = self.new_user()
        code = self.code_for(referrer)
        status, _, body = self.get('/register?ref=' + code)
        self.assertEqual(status, 200)
        self.assertIn('name="ref" value="' + code + '"', body)

    def test_dashboard_shows_referral_link(self):
        email, cookie = self.new_user()
        code = self.code_for(email)
        status, _, body = self.get('/', cookie='velxtria_session=' + cookie)
        self.assertEqual(status, 200)
        self.assertIn('Refer friends', body)
        self.assertIn('/?ref=' + code, body)

    def test_referred_payment_credits_referrer(self):
        import btcpay_mainnet
        referrer, _ = self.new_user()
        code = self.code_for(referrer)
        _USER_N[0] += 1
        email = 'rf%d@example.test' % _USER_N[0]
        status, _, _ = self.post_form(
            '/register', {'email': email, 'password': 'TestPass123456!'},
            cookie='velxtria_ref=' + code)
        self.assertEqual(status, 303)
        referred_id = self.user_id(email)

        def fake(method, path, payload=None):
            if method == 'GET' and path == '/invoices/inv1':
                return settled_invoice('inv1', order_id)
            raise RuntimeError('unexpected fake call %s %s' % (method, path))

        with patch.dict(os.environ, MAINNET_ENV):
            with self.portal.db() as c:
                order_id = btcpay_mainnet.create_order(c, referred_id)
                c.execute("UPDATE btcpay_orders SET invoice_id=?,checkout_url=?,"
                          "status='pending' WHERE order_id=?",
                          ('inv1', 'https://btcpay.example.com/i/inv1', order_id))
            with self.portal.db() as c:
                self.assertTrue(btcpay_mainnet.reconcile(c, referred_id, req=fake))
            with self.portal.db() as c:
                ent = subscriptions.entitlement(c, self.user_id(referrer))
        self.assertEqual(ent['plan'], 'pro')


if __name__ == '__main__':
    unittest.main()
