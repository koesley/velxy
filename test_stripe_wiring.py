"""Tests for the Stripe card-checkout wiring in portal.py: the card form
appears wherever the Bitcoin form does (landing, dashboard, report page,
paywall, account, renewal), POST /stripe/checkout creates a Checkout
session and redirects to it, POST /stripe/check-status reconciles, and
POST /webhooks/stripe activates PRO only after a signature-verified
webhook plus a re-read of the session. Test keys never activate PRO
unless VELXTRIA_STRIPE_ALLOW_TEST_ACTIVATION=1 (set here, tests only).
Run with:
  python -m unittest test_stripe_wiring -v
"""
import hashlib
import hmac
import http.client
import json
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

STRIPE_ENV = {
    'VELXTRIA_STRIPE_SECRET_KEY': 'sk_test_123',
    'VELXTRIA_STRIPE_WEBHOOK_SECRET': 'whsec_test_123',
    'VELXTRIA_ENABLE_STRIPE_CHECKOUT': '1',
    'VELXTRIA_STRIPE_ALLOW_TEST_ACTIVATION': '1',
}

_SESSION_ORDER = {}
_SESSION_N = [0]


def fake_stripe_request(method, path, payload=None):
    """Fake Stripe API: session creation and session reads only. Each
    created session gets a unique id, and the order it belongs to is
    recorded so a later read returns the right metadata."""
    if method == 'POST' and path == '/checkout/sessions':
        _SESSION_N[0] += 1
        sid = 'cs_test_n%d' % _SESSION_N[0]
        order_id = ''
        if isinstance(payload, dict):
            order_id = payload.get('metadata[order_id]', '')
        _SESSION_ORDER[sid] = order_id
        return {'id': sid, 'url': 'https://checkout.stripe.com/pay/' + sid, 'object': 'checkout.session'}
    if method == 'GET' and path.startswith('/checkout/sessions/'):
        sid = path.split('/')[-1]
        return {
            'id': sid, 'object': 'checkout.session',
            'payment_status': 'paid', 'amount_total': 4900,
            'currency': 'usd', 'livemode': False,
            'metadata': {'order_id': _SESSION_ORDER.get(sid, '')},
        }
    raise RuntimeError('unexpected Stripe call %s %s' % (method, path))


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
            "(SELECT id FROM users WHERE email LIKE 'sw%@example.test')")
        c.execute(
            'DELETE FROM sessions WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'sw%@example.test')")
        c.execute(
            "DELETE FROM stripe_orders WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE 'sw%@example.test')")
        c.execute(
            "DELETE FROM stripe_webhook_events WHERE session_id LIKE 'cs_test%'")
        c.execute(
            'DELETE FROM referrals WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'sw%@example.test')")
        c.execute(
            'DELETE FROM referral_signups WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'sw%@example.test')")
        c.execute(
            'DELETE FROM referral_rewards WHERE referred_user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'sw%@example.test')")
        c.execute(
            'DELETE FROM email_outbox WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'sw%@example.test')")
        c.execute(
            'DELETE FROM subscriptions WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'sw%@example.test')")
        c.execute("DELETE FROM users WHERE email LIKE 'sw%@example.test'")
    _ENV.stop()
    _TMP.cleanup()
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class StripeWiringTests(unittest.TestCase):
    def setUp(self):
        import portal
        self.portal = portal
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), portal.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.port = self.server.server_address[1]
        self.env = patch.dict(os.environ, STRIPE_ENV)
        self.env.start()
        self.addCleanup(self.env.stop)

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

    def csrf_for(self, email):
        with self.portal.db() as c:
            row = c.execute(
                'SELECT s.csrf FROM sessions s JOIN users u ON u.id=s.user_id '
                'WHERE u.email=? ORDER BY s.expires DESC LIMIT 1',
                (email,)).fetchone()
            return row[0]

    def sign_in(self, email):
        # /register signs the new account in at once, so the register
        # response already carries the session cookie.
        data = {'email': email, 'password': 'TestPass123456!'}
        status, headers, _ = self.post_form('/register', data)
        self.assertEqual(status, 303)
        match = re.search(r'velxtria_session=([^;]+)', headers.get('Set-Cookie', ''))
        self.assertTrue(match, 'register did not set a session cookie')
        return match.group(1)

    def new_user(self):
        _USER_N[0] += 1
        email = 'sw%d@example.test' % _USER_N[0]
        return email, self.sign_in(email)

    def user_id(self, email):
        with self.portal.db() as c:
            return c.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()[0]

    def make_stripe_order(self, email, status='pending'):
        now = int(time.time())
        with self.portal.db() as c:
            uid = self.user_id(email)
            order_id = 'vx-stripe-' + email.split('@')[0]
            session_id = 'cs_test_' + email.split('@')[0]
            _SESSION_ORDER[session_id] = order_id
            c.execute(
                'INSERT INTO stripe_orders'
                '(order_id,user_id,session_id,checkout_url,status,created_at,settled_at)'
                ' VALUES (?,?,?,?,?,?,?)',
                (order_id, uid, session_id,
                 'https://checkout.stripe.com/pay/' + session_id,
                 status, now, now if status == 'settled' else 0))
            return uid

    def stripe_signature(self, raw_body):
        ts = str(int(time.time()))
        signed = ('%s.' % ts).encode('utf-8') + raw_body
        digest = hmac.new(STRIPE_ENV['VELXTRIA_STRIPE_WEBHOOK_SECRET'].encode('utf-8'),
                          signed, hashlib.sha256).hexdigest()
        return 't=%s,v1=%s' % (ts, digest)

    def test_stripe_verified_source_grants_pro(self):
        import subscriptions
        email, _ = self.new_user()
        uid = self.user_id(email)
        now = int(time.time())
        with self.portal.db() as c:
            c.execute(
                'INSERT INTO subscriptions'
                '(user_id,product_key,pricing_plan,status,source_reference,'
                'period_start,period_end,verified_at,verification_source,updated_at)'
                ' VALUES (?,?,?,?,?,?,?,?,?,?)',
                (uid, subscriptions.PRODUCT_KEY, subscriptions.PRICING_PLAN,
                 'active', 'cs_test_src', now - 100, now + 30 * 86400, now,
                 'stripe_verified', now))
            ent = subscriptions.entitlement(c, uid)
        self.assertEqual(ent['plan'], 'pro')

    def test_dashboard_shows_card_form_when_stripe_enabled(self):
        _, cookie = self.new_user()
        status, _, body = self.get('/', cookie)
        self.assertEqual(status, 200)
        self.assertIn('Pay $49 with card', body)
        self.assertIn('action="/stripe/checkout"', body)

    def test_dashboard_hides_card_form_when_stripe_disabled(self):
        _, cookie = self.new_user()
        with patch.dict(os.environ, {'VELXTRIA_ENABLE_STRIPE_CHECKOUT': '0'}):
            status, _, body = self.get('/', cookie)
        self.assertEqual(status, 200)
        self.assertNotIn('Pay $49 with card', body)
        self.assertNotIn('action="/stripe/checkout"', body)

    def test_checkout_route_creates_session_and_redirects(self):
        email, cookie = self.new_user()
        with patch.object(self.portal.stripe_checkout, 'request',
                          side_effect=fake_stripe_request):
            status, headers, _ = self.post_form(
                '/stripe/checkout', {'csrf': self.csrf_for(email)}, cookie)
        self.assertEqual(status, 303)
        self.assertTrue(headers.get('Location', '').startswith('https://checkout.stripe.com/pay/'))

    def test_checkout_route_disabled_returns_503(self):
        email, cookie = self.new_user()
        with patch.dict(os.environ, {'VELXTRIA_ENABLE_STRIPE_CHECKOUT': '0'}):
            status, _, _ = self.post_form(
                '/stripe/checkout', {'csrf': self.csrf_for(email)}, cookie)
        self.assertEqual(status, 503)

    def test_checkout_route_requires_login(self):
        status, _, _ = self.post_form('/stripe/checkout', {'csrf': 'x'})
        self.assertEqual(status, 401)

    def test_check_status_reconciles_and_activates_pro(self):
        email, cookie = self.new_user()
        uid = self.make_stripe_order(email)
        with patch.object(self.portal.stripe_checkout, 'request',
                          side_effect=fake_stripe_request):
            status, headers, _ = self.post_form(
                '/stripe/check-status', {'csrf': self.csrf_for(email)}, cookie)
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/account')
        with self.portal.db() as c:
            import subscriptions
            ent = subscriptions.entitlement(c, uid)
        self.assertEqual(ent['plan'], 'pro')

    def test_webhook_paid_session_activates_pro(self):
        email, _ = self.new_user()
        uid = self.make_stripe_order(email)
        session_id = 'cs_test_' + email.split('@')[0]
        payload = json.dumps({
            'id': 'evt_test_1', 'type': 'checkout.session.completed',
            'data': {'object': {'id': session_id}},
        }).encode('utf-8')
        sig = self.stripe_signature(payload)
        with patch.object(self.portal.stripe_checkout, 'request',
                          side_effect=fake_stripe_request):
            status, _, body = self.request(
                'POST', '/webhooks/stripe', body=payload,
                content_type='application/json',
                headers={'Stripe-Signature': sig})
        self.assertEqual(status, 200)
        with self.portal.db() as c:
            import subscriptions
            ent = subscriptions.entitlement(c, uid)
        self.assertEqual(ent['plan'], 'pro')

    def test_webhook_bad_signature_rejected(self):
        status, _, _ = self.request(
            'POST', '/webhooks/stripe', body=b'{}',
            content_type='application/json',
            headers={'Stripe-Signature': 't=1,v1=deadbeef'})
        self.assertEqual(status, 401)

    def test_account_shows_stripe_orders(self):
        email, cookie = self.new_user()
        self.make_stripe_order(email)
        status, _, body = self.get('/account', cookie)
        self.assertEqual(status, 200)
        self.assertIn('Card billing', body)
        self.assertIn('vx-stripe-', body)
        self.assertIn('Pay $49 with card', body)

    def test_checkout_feedback_guards_stripe_form(self):
        status, _, body = self.get('/checkout-feedback.js')
        self.assertEqual(status, 200)
        self.assertIn('/stripe/checkout', body)
        self.assertIn('Card payment pending', body)
        self.assertIn('Bitcoin payment pending', body)

    def test_paywall_shows_card_form(self):
        email, cookie = self.new_user()
        # Use up the one free report so the next upload hits the paywall.
        uid = self.user_id(email)
        with self.portal.db() as c:
            c.execute(
                'INSERT INTO reports(id,user_id,filename,created,status,accepted,rejected,digest)'
                ' VALUES (?,?,?,?,?,?,?,?)',
                ('rep-sw-1', uid, 'sales.csv', int(time.time()), 'ready', 6, 3, 'x' * 64))
        status, _, body = self.get('/account', cookie)
        self.assertEqual(status, 200)
        self.assertIn('Pay $49 with card', body)


if __name__ == '__main__':
    unittest.main()
