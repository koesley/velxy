"""Tests for the Stripe card checkout integration.

No real credentials, no network access: the Stripe API is replaced with a
fake that returns canned checkout session payloads. Run with:
  python -m pytest test_stripe_checkout.py -q
"""
import hashlib
import hmac
import json
import os
import sqlite3
import time
import unittest
from unittest.mock import patch

import stripe_checkout
import subscriptions

STRIPE_ENV = {
    'VELXTRIA_STRIPE_SECRET_KEY': 'sk_test_123',
    'VELXTRIA_STRIPE_WEBHOOK_SECRET': 'whsec-123',
    'VELXTRIA_ENABLE_STRIPE_CHECKOUT': '1',
}


def paid_session(session_id, order_id, amount=4900, currency='usd',
                 payment_status='paid', livemode=True, status='complete'):
    return {
        'id': session_id,
        'object': 'checkout.session',
        'payment_status': payment_status,
        'amount_total': amount,
        'currency': currency,
        'livemode': livemode,
        'status': status,
        'metadata': {'order_id': order_id},
    }


def make_fake(sessions):
    """Fake stripe_checkout.request: GET /checkout/sessions/<id> returns a canned payload."""
    def fake(method, path, payload=None):
        if method == 'GET' and path.startswith('/checkout/sessions/'):
            session_id = path.split('/')[-1]
            if session_id in sessions:
                return sessions[session_id]
            raise RuntimeError('session not found')
        if method == 'POST' and path == '/checkout/sessions':
            return {'id': 'cs_test_new', 'url': 'https://checkout.stripe.com/c/pay/cs_test_new'}
        raise RuntimeError('unexpected fake call %s %s' % (method, path))
    return fake


def capturing_session_fake(seen):
    """Fake stripe_checkout.request that records the session-create payload."""
    def fake(method, path, payload=None):
        if method == 'POST' and path == '/checkout/sessions':
            seen['payload'] = payload
            return {'id': 'cs_test_new', 'url': 'https://checkout.stripe.com/c/pay/cs_test_new'}
        raise RuntimeError('unexpected fake call %s %s' % (method, path))
    return fake


class StripeTestCase(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, STRIPE_ENV)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.conn = sqlite3.connect(':memory:')
        self.conn.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL)')
        self.conn.execute("INSERT INTO users(id,email) VALUES (1,'alice@example.com'),(2,'bob@example.com')")
        subscriptions.setup(self.conn)
        stripe_checkout.setup(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def make_pending_order(self, user_id=1, session_id='cs_test_1'):
        order_id = stripe_checkout.create_order(self.conn, user_id)
        self.conn.execute("UPDATE stripe_orders SET session_id=?,checkout_url=?,status='pending' WHERE order_id=?",
                          (session_id, 'https://checkout.stripe.com/c/pay/' + session_id, order_id))
        self.conn.commit()
        return order_id

    # -- configuration guards -------------------------------------------------
    def test_configured_requires_secret_key(self):
        self.assertTrue(stripe_checkout.configured())
        with patch.dict(os.environ, {'VELXTRIA_STRIPE_SECRET_KEY': ''}):
            self.assertFalse(stripe_checkout.configured())
        # A live key is accepted the same way as a test key; the
        # test-activation guard lives in verify_session, not here.
        with patch.dict(os.environ, {'VELXTRIA_STRIPE_SECRET_KEY': 'sk_live_abc'}):
            self.assertTrue(stripe_checkout.configured())

    def test_checkout_enabled_requires_flag(self):
        self.assertTrue(stripe_checkout.checkout_enabled())
        with patch.dict(os.environ, {'VELXTRIA_ENABLE_STRIPE_CHECKOUT': '0'}):
            self.assertFalse(stripe_checkout.checkout_enabled())
        with patch.dict(os.environ, {'VELXTRIA_ENABLE_STRIPE_CHECKOUT': '0', 'VELXTRIA_STRIPE_SECRET_KEY': ''}):
            self.assertFalse(stripe_checkout.checkout_enabled())

    def test_webhook_configured_requires_secret(self):
        self.assertTrue(stripe_checkout.webhook_configured())
        with patch.dict(os.environ, {'VELXTRIA_STRIPE_WEBHOOK_SECRET': ''}):
            self.assertFalse(stripe_checkout.webhook_configured())

    def test_create_order_requires_configuration(self):
        with patch.dict(os.environ, {'VELXTRIA_STRIPE_SECRET_KEY': ''}):
            with self.assertRaises(RuntimeError):
                stripe_checkout.create_order(self.conn, 1)

    def test_setup_creates_both_tables(self):
        tables = {row[0] for row in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        self.assertIn('stripe_orders', tables)
        self.assertIn('stripe_webhook_events', tables)
        # Running setup again is a no-op (creation is idempotent).
        stripe_checkout.setup(self.conn)
        tables = {row[0] for row in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        self.assertIn('stripe_orders', tables)
        self.assertIn('stripe_webhook_events', tables)

    # -- checkout session creation ---------------------------------------------
    def test_create_order_and_checkout_session(self):
        order_id = stripe_checkout.create_order(self.conn, 1)
        self.assertTrue(order_id.startswith('vx-stripe-'))
        seen = {}
        with patch.object(stripe_checkout, 'request', capturing_session_fake(seen)):
            session_id, checkout_url = stripe_checkout.create_checkout_session(order_id)
        self.assertEqual(session_id, 'cs_test_new')
        self.assertTrue(checkout_url.startswith('https://checkout.stripe.com/c/pay/'))
        payload = seen['payload']
        self.assertEqual(payload['mode'], 'payment')
        self.assertEqual(payload['line_items[0][price_data][unit_amount]'], 4900)
        self.assertEqual(payload['line_items[0][price_data][currency]'], 'usd')
        self.assertEqual(payload['line_items[0][price_data][product_data][name]'],
                         'VELXTRIA PRO - 30 Days - 50 Reports')
        self.assertEqual(payload['line_items[0][quantity]'], 1)
        self.assertEqual(payload['metadata[order_id]'], order_id)
        self.assertIn('/account?paid=1', payload['success_url'])
        self.assertTrue(payload['success_url'].endswith('/account?paid=1&method=stripe'))
        self.assertTrue(payload['cancel_url'].endswith('/account'))

    def test_create_checkout_session_requires_session_and_url(self):
        order_id = stripe_checkout.create_order(self.conn, 1)
        def incomplete(_method, _path, _payload=None):
            return {'id': 'cs_test_new'}  # no url
        with patch.object(stripe_checkout, 'request', incomplete):
            with self.assertRaises(RuntimeError):
                stripe_checkout.create_checkout_session(order_id)

    def test_request_sends_form_encoded_bearer_auth(self):
        # The real request() must form-encode the payload and use Bearer auth.
        seen = {}
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return False
            def read(self):
                return b'{"id": "cs_test_x", "url": "https://checkout.stripe.com/c/pay/x"}'
        def fake_urlopen(req, timeout=None):
            seen['url'] = req.full_url
            seen['method'] = req.get_method()
            seen['auth'] = req.headers.get('Authorization')
            seen['content_type'] = req.headers.get('Content-type')
            seen['body'] = req.data.decode('utf-8') if req.data else ''
            return FakeResponse()
        with patch('urllib.request.urlopen', fake_urlopen):
            stripe_checkout.request('POST', '/checkout/sessions', {'mode': 'payment', 'a[0][b]': 'c'})
        self.assertEqual(seen['url'], 'https://api.stripe.com/v1/checkout/sessions')
        self.assertEqual(seen['method'], 'POST')
        self.assertEqual(seen['auth'], 'Bearer sk_test_123')
        self.assertEqual(seen['content_type'], 'application/x-www-form-urlencoded')
        self.assertIn('mode=payment', seen['body'])
        self.assertIn('a%5B0%5D%5Bb%5D=c', seen['body'])

    def test_request_network_failure_fails_closed(self):
        with patch('urllib.request.urlopen', side_effect=OSError('tls handshake failed')):
            with self.assertRaises(RuntimeError):
                stripe_checkout.request('GET', '/checkout/sessions/cs_test_1')

    # -- verify_session ----------------------------------------------------------
    def test_verify_session_paid_and_correct(self):
        order_id = 'vx-stripe-abc'
        ok, reason = stripe_checkout.verify_session(
            paid_session('cs_test_1', order_id), order_id, 'cs_test_1')
        self.assertTrue(ok)
        self.assertEqual(reason, '')

    def test_verify_session_unpaid(self):
        order_id = 'vx-stripe-abc'
        ok, _ = stripe_checkout.verify_session(
            paid_session('cs_test_1', order_id, payment_status='unpaid'), order_id, 'cs_test_1')
        self.assertFalse(ok)

    def test_verify_session_wrong_amount(self):
        order_id = 'vx-stripe-abc'
        ok, _ = stripe_checkout.verify_session(
            paid_session('cs_test_1', order_id, amount=4800), order_id, 'cs_test_1')
        self.assertFalse(ok)

    def test_verify_session_wrong_currency(self):
        order_id = 'vx-stripe-abc'
        ok, _ = stripe_checkout.verify_session(
            paid_session('cs_test_1', order_id, currency='eur'), order_id, 'cs_test_1')
        self.assertFalse(ok)

    def test_verify_session_wrong_order(self):
        ok, _ = stripe_checkout.verify_session(
            paid_session('cs_test_1', 'vx-stripe-other'), 'vx-stripe-abc', 'cs_test_1')
        self.assertFalse(ok)

    def test_verify_session_wrong_session_id(self):
        order_id = 'vx-stripe-abc'
        ok, _ = stripe_checkout.verify_session(
            paid_session('cs_test_1', order_id), order_id, 'cs_test_other')
        self.assertFalse(ok)

    def test_verify_session_non_dict(self):
        ok, _ = stripe_checkout.verify_session('not-a-dict', 'vx-stripe-abc')
        self.assertFalse(ok)
        ok, _ = stripe_checkout.verify_session(None, 'vx-stripe-abc')
        self.assertFalse(ok)

    def test_verify_session_test_mode_refused_by_default(self):
        order_id = 'vx-stripe-abc'
        session = paid_session('cs_test_1', order_id, livemode=False)
        ok, reason = stripe_checkout.verify_session(session, order_id, 'cs_test_1')
        self.assertFalse(ok)
        self.assertEqual(reason, 'test mode session cannot activate PRO')

    def test_verify_session_test_mode_allowed_with_opt_in(self):
        order_id = 'vx-stripe-abc'
        session = paid_session('cs_test_1', order_id, livemode=False)
        with patch.dict(os.environ, {'VELXTRIA_STRIPE_ALLOW_TEST_ACTIVATION': '1'}):
            ok, reason = stripe_checkout.verify_session(session, order_id, 'cs_test_1')
        self.assertTrue(ok)
        self.assertEqual(reason, '')

    # -- successful payment -------------------------------------------------------
    def test_successful_payment_activates_pro(self):
        order_id = self.make_pending_order()
        fake = make_fake({'cs_test_1': paid_session('cs_test_1', order_id)})
        self.assertTrue(stripe_checkout.reconcile(self.conn, 1, req=fake))
        self.conn.commit()
        row = self.conn.execute(
            'SELECT status,verification_source,source_reference FROM subscriptions WHERE user_id=1').fetchone()
        self.assertEqual(row, ('active', 'stripe_verified', 'cs_test_1'))
        order = self.conn.execute("SELECT status FROM stripe_orders WHERE order_id=?", (order_id,)).fetchone()
        self.assertEqual(order[0], 'settled')

    def test_claim_and_activate_is_idempotent(self):
        order_id = self.make_pending_order()
        self.assertTrue(stripe_checkout._claim_and_activate(self.conn, 1, order_id, 'cs_test_1'))
        self.conn.commit()
        end_first = self.conn.execute('SELECT period_end FROM subscriptions WHERE user_id=1').fetchone()[0]
        # Second and third claims must not extend the period or re-activate.
        self.assertFalse(stripe_checkout._claim_and_activate(self.conn, 1, order_id, 'cs_test_1'))
        self.assertFalse(stripe_checkout._claim_and_activate(self.conn, 1, order_id, 'cs_test_1'))
        self.conn.commit()
        end_later = self.conn.execute('SELECT period_end FROM subscriptions WHERE user_id=1').fetchone()[0]
        self.assertEqual(end_first, end_later)
        row = self.conn.execute(
            'SELECT status,verification_source FROM subscriptions WHERE user_id=1').fetchone()
        self.assertEqual(row, ('active', 'stripe_verified'))

    def test_repeated_reconcile_is_idempotent(self):
        order_id = self.make_pending_order()
        fake = make_fake({'cs_test_1': paid_session('cs_test_1', order_id)})
        self.assertTrue(stripe_checkout.reconcile(self.conn, 1, req=fake))
        self.conn.commit()
        end_first = self.conn.execute('SELECT period_end FROM subscriptions WHERE user_id=1').fetchone()[0]
        self.assertFalse(stripe_checkout.reconcile(self.conn, 1, req=fake))
        self.conn.commit()
        end_later = self.conn.execute('SELECT period_end FROM subscriptions WHERE user_id=1').fetchone()[0]
        self.assertEqual(end_first, end_later)

    def test_other_user_cannot_activate(self):
        order_id = self.make_pending_order(user_id=1)
        fake = make_fake({'cs_test_1': paid_session('cs_test_1', order_id)})
        # Bob reconciles; Alice's order must be untouched and Bob gets nothing.
        self.assertFalse(stripe_checkout.reconcile(self.conn, 2, req=fake))
        self.conn.commit()
        order = self.conn.execute("SELECT status FROM stripe_orders WHERE order_id=?", (order_id,)).fetchone()
        self.assertEqual(order[0], 'pending')
        row = self.conn.execute('SELECT user_id FROM subscriptions WHERE user_id=2').fetchone()
        self.assertIsNone(row)

    # -- failed / terminal payments -------------------------------------------------
    def test_expired_session_marks_expired_no_access(self):
        order_id = self.make_pending_order()
        fake = make_fake({'cs_test_1': paid_session('cs_test_1', order_id, payment_status='unpaid', status='expired')})
        self.assertFalse(stripe_checkout.reconcile(self.conn, 1, req=fake))
        self.conn.commit()
        order = self.conn.execute("SELECT status FROM stripe_orders WHERE order_id=?", (order_id,)).fetchone()
        self.assertEqual(order[0], 'expired')
        row = self.conn.execute('SELECT user_id FROM subscriptions WHERE user_id=1').fetchone()
        self.assertIsNone(row)

    def test_unpaid_session_stays_pending(self):
        order_id = self.make_pending_order()
        fake = make_fake({'cs_test_1': paid_session('cs_test_1', order_id, payment_status='unpaid', status='open')})
        self.assertFalse(stripe_checkout.reconcile(self.conn, 1, req=fake))
        self.conn.commit()
        order = self.conn.execute("SELECT status FROM stripe_orders WHERE order_id=?", (order_id,)).fetchone()
        self.assertEqual(order[0], 'pending')

    def test_test_mode_session_never_activates_via_reconcile(self):
        order_id = self.make_pending_order()
        fake = make_fake({'cs_test_1': paid_session('cs_test_1', order_id, livemode=False)})
        self.assertFalse(stripe_checkout.reconcile(self.conn, 1, req=fake))
        self.conn.commit()
        row = self.conn.execute('SELECT user_id FROM subscriptions WHERE user_id=1').fetchone()
        self.assertIsNone(row)

    def test_reconcile_unavailable_leaves_pending(self):
        order_id = self.make_pending_order()
        def broken(_method, _path, _payload=None):
            raise OSError('tls handshake failed')
        self.assertFalse(stripe_checkout.reconcile(self.conn, 1, req=broken))
        self.conn.commit()
        order = self.conn.execute("SELECT status FROM stripe_orders WHERE order_id=?", (order_id,)).fetchone()
        self.assertEqual(order[0], 'pending')

    def test_latest_and_pending_orders(self):
        self.assertIsNone(stripe_checkout.latest_order(self.conn, 1))
        self.assertIsNone(stripe_checkout.pending_order(self.conn, 1))
        order_id = self.make_pending_order()
        latest = stripe_checkout.latest_order(self.conn, 1)
        self.assertEqual(latest['order_id'], order_id)
        self.assertEqual(latest['status'], 'pending')
        pending = stripe_checkout.pending_order(self.conn, 1)
        self.assertEqual(pending['order_id'], order_id)
        self.assertIn('checkout_url', pending)

    # -- webhook signature ------------------------------------------------------------
    def _signed(self, payload, secret=b'whsec-123', ts=None):
        raw = json.dumps(payload).encode('utf-8')
        ts = int(time.time()) if ts is None else ts
        signed = ('%d.' % ts).encode('utf-8') + raw
        sig = 't=%d,v1=%s' % (ts, hmac.new(secret, signed, hashlib.sha256).hexdigest())
        return raw, sig

    def test_webhook_signature_verification(self):
        raw, sig = self._signed({'type': 'checkout.session.completed'})
        self.assertTrue(stripe_checkout.verify_webhook_signature(raw, sig))
        self.assertFalse(stripe_checkout.verify_webhook_signature(raw + b'x', sig))
        self.assertFalse(stripe_checkout.verify_webhook_signature(raw, 't=1,v1=deadbeef'))
        self.assertFalse(stripe_checkout.verify_webhook_signature(raw, ''))
        self.assertFalse(stripe_checkout.verify_webhook_signature(raw, None))
        with patch.dict(os.environ, {'VELXTRIA_STRIPE_WEBHOOK_SECRET': ''}):
            self.assertFalse(stripe_checkout.verify_webhook_signature(raw, sig))

    def test_webhook_signature_wrong_secret_fails(self):
        raw, _sig = self._signed({'type': 'checkout.session.completed'}, secret=b'whsec-other')
        self.assertFalse(stripe_checkout.verify_webhook_signature(raw, _sig))

    def test_webhook_signature_rejects_stale_timestamp(self):
        raw, sig = self._signed({'type': 'checkout.session.completed'},
                                ts=int(time.time()) - 301)
        self.assertFalse(stripe_checkout.verify_webhook_signature(raw, sig))

    def test_webhook_signature_rejects_malformed_header(self):
        raw, _sig = self._signed({'type': 'checkout.session.completed'})
        # No t= part.
        self.assertFalse(stripe_checkout.verify_webhook_signature(raw, 'v1=deadbeef'))
        # No v1= part.
        self.assertFalse(stripe_checkout.verify_webhook_signature(
            raw, 't=%d' % int(time.time())))
        # Non-integer timestamp.
        self.assertFalse(stripe_checkout.verify_webhook_signature(raw, 't=abc,v1=deadbeef'))

    # -- webhook handling ---------------------------------------------------------------
    def _completed_event(self, session_id, order_id):
        return {'id': 'evt_1', 'type': 'checkout.session.completed',
                'data': {'object': paid_session(session_id, order_id)}}

    def test_webhook_bad_signature_rejected(self):
        order_id = self.make_pending_order()
        raw, _sig = self._signed(self._completed_event('cs_test_1', order_id))
        status, _msg = stripe_checkout.handle_webhook(self.conn, raw, 't=1,v1=deadbeef')
        self.assertEqual(status, 401)
        row = self.conn.execute('SELECT user_id FROM subscriptions WHERE user_id=1').fetchone()
        self.assertIsNone(row)

    def test_webhook_without_secret_rejected(self):
        order_id = self.make_pending_order()
        raw, sig = self._signed(self._completed_event('cs_test_1', order_id))
        with patch.dict(os.environ, {'VELXTRIA_STRIPE_WEBHOOK_SECRET': ''}):
            status, _msg = stripe_checkout.handle_webhook(self.conn, raw, sig)
        self.assertEqual(status, 401)

    def test_webhook_not_configured_returns_503(self):
        # Signature verifies (webhook secret present) but the secret key is
        # missing, so the webhook endpoint itself is not configured.
        order_id = self.make_pending_order()
        raw, sig = self._signed(self._completed_event('cs_test_1', order_id))
        with patch.dict(os.environ, {'VELXTRIA_STRIPE_SECRET_KEY': ''}):
            status, _msg = stripe_checkout.handle_webhook(self.conn, raw, sig)
        self.assertEqual(status, 503)

    def test_webhook_unknown_session_ignored(self):
        raw, sig = self._signed(self._completed_event('cs_test_nope', 'vx-stripe-nope'))
        status, _msg = stripe_checkout.handle_webhook(self.conn, raw, sig)
        self.assertEqual(status, 200)
        row = self.conn.execute('SELECT user_id FROM subscriptions WHERE user_id=1').fetchone()
        self.assertIsNone(row)

    def test_webhook_completed_activates_via_reverification(self):
        order_id = self.make_pending_order()
        fake = make_fake({'cs_test_1': paid_session('cs_test_1', order_id)})
        raw, sig = self._signed(self._completed_event('cs_test_1', order_id))
        with patch.object(stripe_checkout, 'request', fake):
            status, _msg = stripe_checkout.handle_webhook(self.conn, raw, sig)
        self.assertEqual(status, 200)
        self.conn.commit()
        row = self.conn.execute(
            'SELECT status,verification_source FROM subscriptions WHERE user_id=1').fetchone()
        self.assertEqual(row, ('active', 'stripe_verified'))

    def test_webhook_async_payment_succeeded_activates(self):
        order_id = self.make_pending_order()
        fake = make_fake({'cs_test_1': paid_session('cs_test_1', order_id)})
        payload = {'id': 'evt_2', 'type': 'checkout.session.async_payment_succeeded',
                   'data': {'object': paid_session('cs_test_1', order_id)}}
        raw, sig = self._signed(payload)
        with patch.object(stripe_checkout, 'request', fake):
            status, _msg = stripe_checkout.handle_webhook(self.conn, raw, sig)
        self.assertEqual(status, 200)
        self.conn.commit()
        row = self.conn.execute(
            'SELECT status FROM subscriptions WHERE user_id=1').fetchone()
        self.assertEqual(row, ('active',))

    def test_webhook_duplicate_delivery_ignored(self):
        order_id = self.make_pending_order()
        fake = make_fake({'cs_test_1': paid_session('cs_test_1', order_id)})
        raw, sig = self._signed(self._completed_event('cs_test_1', order_id))
        with patch.object(stripe_checkout, 'request', fake):
            first = stripe_checkout.handle_webhook(self.conn, raw, sig)
            self.conn.commit()
            end_first = self.conn.execute('SELECT period_end FROM subscriptions WHERE user_id=1').fetchone()[0]
            second = stripe_checkout.handle_webhook(self.conn, raw, sig)
            self.conn.commit()
        self.assertEqual(first[0], 200)
        self.assertEqual(second, (200, 'Duplicate delivery ignored'))
        end_later = self.conn.execute('SELECT period_end FROM subscriptions WHERE user_id=1').fetchone()[0]
        self.assertEqual(end_first, end_later)

    def test_webhook_other_event_type_ignored_without_fingerprint(self):
        order_id = self.make_pending_order()
        payload = {'id': 'evt_3', 'type': 'payment_intent.succeeded',
                   'data': {'object': paid_session('cs_test_1', order_id)}}
        raw, sig = self._signed(payload)
        fake = make_fake({'cs_test_1': paid_session('cs_test_1', order_id)})
        with patch.object(stripe_checkout, 'request', fake):
            status, msg = stripe_checkout.handle_webhook(self.conn, raw, sig)
        self.assertEqual(status, 200)
        self.assertEqual(msg, 'Ignored: event type')
        # No fingerprint recorded: the same delivery is ignored again, not
        # treated as a duplicate.
        with patch.object(stripe_checkout, 'request', fake):
            status, msg = stripe_checkout.handle_webhook(self.conn, raw, sig)
        self.assertEqual((status, msg), (200, 'Ignored: event type'))
        count = self.conn.execute('SELECT count(*) FROM stripe_webhook_events').fetchone()[0]
        self.assertEqual(count, 0)
        row = self.conn.execute('SELECT user_id FROM subscriptions WHERE user_id=1').fetchone()
        self.assertIsNone(row)

    def test_webhook_never_trusts_payload_alone(self):
        # A signed webhook claiming completion must NOT activate PRO when the
        # Stripe API itself says the session is still unpaid.
        order_id = self.make_pending_order()
        fake = make_fake({'cs_test_1': paid_session('cs_test_1', order_id, payment_status='unpaid', status='open')})
        raw, sig = self._signed(self._completed_event('cs_test_1', order_id))
        with patch.object(stripe_checkout, 'request', fake):
            status, _msg = stripe_checkout.handle_webhook(self.conn, raw, sig)
        self.assertEqual(status, 200)
        row = self.conn.execute('SELECT user_id FROM subscriptions WHERE user_id=1').fetchone()
        self.assertIsNone(row)

    def test_webhook_bad_payload_rejected(self):
        raw = b'not json'
        ts = int(time.time())
        signed = ('%d.' % ts).encode('utf-8') + raw
        sig = 't=%d,v1=%s' % (ts, hmac.new(b'whsec-123', signed, hashlib.sha256).hexdigest())
        status, _msg = stripe_checkout.handle_webhook(self.conn, raw, sig)
        self.assertEqual(status, 400)

    def test_webhook_no_session_ignored(self):
        raw, sig = self._signed({'id': 'evt_4', 'type': 'checkout.session.completed',
                                 'data': {'object': {}}})
        status, msg = stripe_checkout.handle_webhook(self.conn, raw, sig)
        self.assertEqual((status, msg), (200, 'Ignored: no session'))


if __name__ == '__main__':
    unittest.main()
