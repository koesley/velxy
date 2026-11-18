"""Tests for the production (mainnet) BTCPay integration.

No real credentials, no network access: the BTCPay API is replaced with a
fake that returns canned invoice payloads. Run with:
  python -m unittest test_btcpay_mainnet -v
"""
import hashlib
import hmac
import json
import os
import sqlite3
import unittest
from unittest.mock import patch

import btcpay_mainnet
import subscriptions

MAINNET_ENV = {
    'VELXTRIA_BTCPAY_MAINNET_URL': 'https://btcpay.example.com',
    'VELXTRIA_BTCPAY_MAINNET_STORE_ID': 'store123',
    'VELXTRIA_BTCPAY_MAINNET_API_KEY': 'api-key-123',
    'VELXTRIA_BTCPAY_MAINNET_WEBHOOK_SECRET': 'whsec-123',
    'VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT': '1',
}


def settled_invoice(invoice_id, order_id, amount='49.00', currency='USD', status='Settled', refunds=None):
    payload = {
        'id': invoice_id,
        'storeId': 'store123',
        'amount': amount,
        'currency': currency,
        'status': status,
        'metadata': {'orderId': order_id, 'itemDesc': 'VELXTRIA PRO - 30 Days - 50 Reports'},
        'checkoutLink': 'https://btcpay.example.com/i/' + invoice_id,
    }
    if refunds is not None:
        payload['refunds'] = refunds
    return payload


def make_fake(invoices):
    """Fake btcpay_mainnet.request: GET /invoices/<id> returns a canned payload."""
    def fake(method, path, payload=None):
        if method == 'GET' and path.startswith('/invoices/'):
            invoice_id = path.split('/')[-1]
            if invoice_id in invoices:
                return invoices[invoice_id]
            raise RuntimeError('invoice not found')
        if method == 'POST' and path == '/invoices':
            return {'id': 'inv-new', 'checkoutLink': 'https://btcpay.example.com/i/inv-new'}
        if method == 'GET' and path == '/payment-methods/BTC':
            return {'enabled': True, 'network': 'BTC'}
        raise RuntimeError('unexpected fake call %s %s' % (method, path))
    return fake


class MainnetTestCase(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, MAINNET_ENV)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.conn = sqlite3.connect(':memory:')
        self.conn.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL)')
        self.conn.execute("INSERT INTO users(id,email) VALUES (1,'alice@example.com'),(2,'bob@example.com')")
        subscriptions.setup(self.conn)
        btcpay_mainnet.setup(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def make_pending_order(self, user_id=1, invoice_id='inv1'):
        order_id = btcpay_mainnet.create_order(self.conn, user_id)
        self.conn.execute("UPDATE btcpay_orders SET invoice_id=?,checkout_url=?,status='pending' WHERE order_id=?",
                          (invoice_id, 'https://btcpay.example.com/i/' + invoice_id, order_id))
        self.conn.commit()
        return order_id

    # -- configuration guards -------------------------------------------------
    def test_configured_requires_mainnet_host(self):
        self.assertTrue(btcpay_mainnet.configured())
        with patch.dict(os.environ, {'VELXTRIA_BTCPAY_MAINNET_URL': ''}):
            self.assertFalse(btcpay_mainnet.configured())
        with patch.dict(os.environ, {'VELXTRIA_BTCPAY_MAINNET_URL': 'https://testnet.demo.btcpayserver.org'}):
            self.assertFalse(btcpay_mainnet.configured())
        with patch.dict(os.environ, {'VELXTRIA_BTCPAY_MAINNET_URL': 'https://my-testnet-node.example.com'}):
            self.assertFalse(btcpay_mainnet.configured())
        with patch.dict(os.environ, {'VELXTRIA_BTCPAY_MAINNET_URL': 'http://btcpay.example.com'}):
            self.assertFalse(btcpay_mainnet.configured())
        with patch.dict(os.environ, {'VELXTRIA_BTCPAY_MAINNET_API_KEY': ''}):
            self.assertFalse(btcpay_mainnet.configured())
        with patch.dict(os.environ, {'VELXTRIA_BTCPAY_MAINNET_STORE_ID': ''}):
            self.assertFalse(btcpay_mainnet.configured())

    def test_checkout_enabled_requires_flag(self):
        self.assertTrue(btcpay_mainnet.checkout_enabled())
        with patch.dict(os.environ, {'VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT': '0'}):
            self.assertFalse(btcpay_mainnet.checkout_enabled())

    def test_issue_invoice_uses_mainnet_host(self):
        order_id = btcpay_mainnet.create_order(self.conn, 1)
        with patch.object(btcpay_mainnet, 'request', make_fake({})):
            invoice_id, checkout_url = btcpay_mainnet.issue_invoice(order_id)
        self.assertEqual(invoice_id, 'inv-new')
        self.assertTrue(checkout_url.startswith('https://btcpay.example.com/i/'))

    def test_setup_adds_network_column(self):
        cols = [row[1] for row in self.conn.execute('PRAGMA table_info(btcpay_orders)').fetchall()]
        self.assertIn('network', cols)
        # Running setup again is a no-op (migration is idempotent).
        btcpay_mainnet.setup(self.conn)
        cols = [row[1] for row in self.conn.execute('PRAGMA table_info(btcpay_orders)').fetchall()]
        self.assertEqual(cols.count('network'), 1)

    # -- successful payment ----------------------------------------------------
    def test_successful_payment_activates_pro(self):
        order_id = self.make_pending_order()
        fake = make_fake({'inv1': settled_invoice('inv1', order_id)})
        self.assertTrue(btcpay_mainnet.reconcile(self.conn, 1, req=fake))
        self.conn.commit()
        ent = subscriptions.entitlement(self.conn, 1)
        self.assertEqual(ent['plan'], 'pro')
        row = self.conn.execute('SELECT status,verification_source FROM subscriptions WHERE user_id=1').fetchone()
        self.assertEqual(row, ('active', 'btcpay_mainnet_verified'))
        order = self.conn.execute("SELECT status FROM btcpay_orders WHERE order_id=?", (order_id,)).fetchone()
        self.assertEqual(order[0], 'settled')

    def test_repeated_reconcile_is_idempotent(self):
        order_id = self.make_pending_order()
        fake = make_fake({'inv1': settled_invoice('inv1', order_id)})
        self.assertTrue(btcpay_mainnet.reconcile(self.conn, 1, req=fake))
        self.conn.commit()
        end_first = self.conn.execute('SELECT period_end FROM subscriptions WHERE user_id=1').fetchone()[0]
        # Second and third runs must not extend the period or re-activate.
        self.assertFalse(btcpay_mainnet.reconcile(self.conn, 1, req=fake))
        self.assertFalse(btcpay_mainnet.reconcile(self.conn, 1, req=fake))
        self.conn.commit()
        end_later = self.conn.execute('SELECT period_end FROM subscriptions WHERE user_id=1').fetchone()[0]
        self.assertEqual(end_first, end_later)

    # -- failed / terminal payments ----------------------------------------------
    def test_expired_invoice_marks_expired_no_access(self):
        order_id = self.make_pending_order()
        fake = make_fake({'inv1': settled_invoice('inv1', order_id, status='Expired')})
        self.assertFalse(btcpay_mainnet.reconcile(self.conn, 1, req=fake))
        self.conn.commit()
        order = self.conn.execute("SELECT status FROM btcpay_orders WHERE order_id=?", (order_id,)).fetchone()
        self.assertEqual(order[0], 'expired')
        self.assertEqual(subscriptions.entitlement(self.conn, 1)['plan'], 'demo')

    def test_invalid_invoice_marks_invalid_no_access(self):
        order_id = self.make_pending_order()
        fake = make_fake({'inv1': settled_invoice('inv1', order_id, status='Invalid')})
        self.assertFalse(btcpay_mainnet.reconcile(self.conn, 1, req=fake))
        self.conn.commit()
        order = self.conn.execute("SELECT status FROM btcpay_orders WHERE order_id=?", (order_id,)).fetchone()
        self.assertEqual(order[0], 'invalid')
        self.assertEqual(subscriptions.entitlement(self.conn, 1)['plan'], 'demo')

    def test_processing_invoice_stays_pending(self):
        order_id = self.make_pending_order()
        fake = make_fake({'inv1': settled_invoice('inv1', order_id, status='Processing')})
        self.assertFalse(btcpay_mainnet.reconcile(self.conn, 1, req=fake))
        self.conn.commit()
        order = self.conn.execute("SELECT status FROM btcpay_orders WHERE order_id=?", (order_id,)).fetchone()
        self.assertEqual(order[0], 'pending')
        self.assertEqual(subscriptions.entitlement(self.conn, 1)['plan'], 'demo')

    # -- invalid invoices ---------------------------------------------------------
    def test_wrong_amount_no_access(self):
        order_id = self.make_pending_order()
        fake = make_fake({'inv1': settled_invoice('inv1', order_id, amount='48.99')})
        self.assertFalse(btcpay_mainnet.reconcile(self.conn, 1, req=fake))
        self.assertEqual(subscriptions.entitlement(self.conn, 1)['plan'], 'demo')

    def test_wrong_currency_no_access(self):
        order_id = self.make_pending_order()
        fake = make_fake({'inv1': settled_invoice('inv1', order_id, currency='EUR')})
        self.assertFalse(btcpay_mainnet.reconcile(self.conn, 1, req=fake))
        self.assertEqual(subscriptions.entitlement(self.conn, 1)['plan'], 'demo')

    def test_wrong_order_no_access(self):
        order_id = self.make_pending_order()
        fake = make_fake({'inv1': settled_invoice('inv1', 'vx-someone-elses-order')})
        self.assertFalse(btcpay_mainnet.reconcile(self.conn, 1, req=fake))
        self.assertEqual(subscriptions.entitlement(self.conn, 1)['plan'], 'demo')

    def test_wrong_invoice_id_no_access(self):
        order_id = self.make_pending_order()
        payload = settled_invoice('inv-other', order_id)
        fake = make_fake({'inv1': payload})
        self.assertFalse(btcpay_mainnet.reconcile(self.conn, 1, req=fake))
        self.assertEqual(subscriptions.entitlement(self.conn, 1)['plan'], 'demo')

    def test_refunded_invoice_no_access(self):
        order_id = self.make_pending_order()
        payload = settled_invoice('inv1', order_id, refunds=[{'id': 'refund1'}])
        fake = make_fake({'inv1': payload})
        self.assertFalse(btcpay_mainnet.reconcile(self.conn, 1, req=fake))
        self.assertEqual(subscriptions.entitlement(self.conn, 1)['plan'], 'demo')

    def test_malformed_invoice_no_access(self):
        order_id = self.make_pending_order()
        fake = make_fake({'inv1': {'id': 'inv1'}})
        self.assertFalse(btcpay_mainnet.reconcile(self.conn, 1, req=fake))
        self.assertEqual(subscriptions.entitlement(self.conn, 1)['plan'], 'demo')
        ok, _reason = btcpay_mainnet.verify_invoice('not-a-dict', order_id)
        self.assertFalse(ok)

    def test_network_failure_fails_closed(self):
        # A TLS/DNS/socket failure inside the BTCPay call must surface as a
        # RuntimeError (never crash the handler) and grant nothing.
        order_id = self.make_pending_order()
        with patch('urllib.request.urlopen', side_effect=OSError('tls handshake failed')):
            with self.assertRaises(RuntimeError):
                btcpay_mainnet.issue_invoice(order_id)
        def broken(_method, _path, _payload=None):
            raise OSError('tls handshake failed')
        self.assertFalse(btcpay_mainnet.reconcile(self.conn, 1, req=broken))
        self.assertEqual(subscriptions.entitlement(self.conn, 1)['plan'], 'demo')

    # -- unauthorized access ---------------------------------------------------------
    def test_other_user_cannot_activate(self):
        order_id = self.make_pending_order(user_id=1)
        fake = make_fake({'inv1': settled_invoice('inv1', order_id)})
        # Bob reconciles; Alice's order must be untouched and Bob gets nothing.
        self.assertFalse(btcpay_mainnet.reconcile(self.conn, 2, req=fake))
        self.conn.commit()
        order = self.conn.execute("SELECT status FROM btcpay_orders WHERE order_id=?", (order_id,)).fetchone()
        self.assertEqual(order[0], 'pending')
        self.assertEqual(subscriptions.entitlement(self.conn, 2)['plan'], 'demo')
        self.assertEqual(subscriptions.entitlement(self.conn, 1)['plan'], 'demo')

    # -- webhooks ----------------------------------------------------------------------
    def _signed(self, payload):
        raw = json.dumps(payload).encode('utf-8')
        sig = 'sha256=' + hmac.new(b'whsec-123', raw, hashlib.sha256).hexdigest()
        return raw, sig

    def test_webhook_signature_verification(self):
        raw, sig = self._signed({'type': 'InvoicePaymentSettled', 'invoiceId': 'inv1'})
        self.assertTrue(btcpay_mainnet.verify_webhook_signature(raw, sig))
        self.assertFalse(btcpay_mainnet.verify_webhook_signature(raw + b'x', sig))
        self.assertFalse(btcpay_mainnet.verify_webhook_signature(raw, 'sha256=deadbeef'))
        self.assertFalse(btcpay_mainnet.verify_webhook_signature(raw, ''))
        self.assertFalse(btcpay_mainnet.verify_webhook_signature(raw, None))
        with patch.dict(os.environ, {'VELXTRIA_BTCPAY_MAINNET_WEBHOOK_SECRET': ''}):
            self.assertFalse(btcpay_mainnet.verify_webhook_signature(raw, sig))

    def test_webhook_activates_via_reverification(self):
        order_id = self.make_pending_order()
        fake = make_fake({'inv1': settled_invoice('inv1', order_id)})
        raw, sig = self._signed({'type': 'InvoicePaymentSettled', 'invoiceId': 'inv1'})
        with patch.object(btcpay_mainnet, 'request', fake):
            status, _msg = btcpay_mainnet.handle_webhook(self.conn, raw, sig)
        self.assertEqual(status, 200)
        self.conn.commit()
        self.assertEqual(subscriptions.entitlement(self.conn, 1)['plan'], 'pro')

    def test_webhook_duplicate_delivery_ignored(self):
        order_id = self.make_pending_order()
        fake = make_fake({'inv1': settled_invoice('inv1', order_id)})
        raw, sig = self._signed({'type': 'InvoicePaymentSettled', 'invoiceId': 'inv1'})
        with patch.object(btcpay_mainnet, 'request', fake):
            first = btcpay_mainnet.handle_webhook(self.conn, raw, sig)
            self.conn.commit()
            end_first = self.conn.execute('SELECT period_end FROM subscriptions WHERE user_id=1').fetchone()[0]
            second = btcpay_mainnet.handle_webhook(self.conn, raw, sig)
            self.conn.commit()
        self.assertEqual(first[0], 200)
        self.assertEqual(second, (200, 'Duplicate delivery ignored'))
        end_later = self.conn.execute('SELECT period_end FROM subscriptions WHERE user_id=1').fetchone()[0]
        self.assertEqual(end_first, end_later)

    def test_webhook_bad_signature_rejected(self):
        order_id = self.make_pending_order()
        raw, _sig = self._signed({'type': 'InvoicePaymentSettled', 'invoiceId': 'inv1'})
        status, _msg = btcpay_mainnet.handle_webhook(self.conn, raw, 'sha256=deadbeef')
        self.assertEqual(status, 401)
        self.assertEqual(subscriptions.entitlement(self.conn, 1)['plan'], 'demo')

    def test_webhook_unknown_invoice_ignored(self):
        raw, sig = self._signed({'type': 'InvoicePaymentSettled', 'invoiceId': 'inv-nope'})
        status, _msg = btcpay_mainnet.handle_webhook(self.conn, raw, sig)
        self.assertEqual(status, 200)
        self.assertEqual(subscriptions.entitlement(self.conn, 1)['plan'], 'demo')

    def test_webhook_without_secret_fails_closed(self):
        raw, sig = self._signed({'type': 'InvoicePaymentSettled', 'invoiceId': 'inv1'})
        with patch.dict(os.environ, {'VELXTRIA_BTCPAY_MAINNET_WEBHOOK_SECRET': ''}):
            status, _msg = btcpay_mainnet.handle_webhook(self.conn, raw, sig)
        self.assertEqual(status, 503)

    def test_webhook_never_trusts_payload_alone(self):
        # A signed webhook claiming settlement must NOT activate PRO when the
        # BTCPay API itself says the invoice is still unpaid.
        order_id = self.make_pending_order()
        fake = make_fake({'inv1': settled_invoice('inv1', order_id, status='Processing')})
        raw, sig = self._signed({'type': 'InvoicePaymentSettled', 'invoiceId': 'inv1'})
        with patch.object(btcpay_mainnet, 'request', fake):
            status, _msg = btcpay_mainnet.handle_webhook(self.conn, raw, sig)
        self.assertEqual(status, 200)
        self.assertEqual(subscriptions.entitlement(self.conn, 1)['plan'], 'demo')

    # -- mainnet support check ---------------------------------------------------------
    def test_mainnet_support_check(self):
        with patch.object(btcpay_mainnet, 'request', make_fake({})):
            check = btcpay_mainnet.mainnet_support_check()
        self.assertTrue(check['ok'])
        self.assertTrue(check['btc_enabled'])
        self.assertEqual(check['host'], 'https://btcpay.example.com')
        with patch.dict(os.environ, {'VELXTRIA_BTCPAY_MAINNET_URL': 'https://testnet.demo.btcpayserver.org'}):
            check = btcpay_mainnet.mainnet_support_check()
        self.assertFalse(check['ok'])


if __name__ == '__main__':
    unittest.main()
