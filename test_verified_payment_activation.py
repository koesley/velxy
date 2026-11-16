"""Verified testnet payment activation and idempotency regression tests.

These tests mock BTCPay's authenticated server API. They do not prove a
production provider or Payhip subscription integration.
"""
import sqlite3
import unittest
from unittest.mock import patch
import btcpay_integration as btc
import subscriptions

class VerifiedTestnetPaymentTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(':memory:')
        self.c.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, email TEXT)")
        self.c.execute("INSERT INTO users VALUES(1,'buyer@example.com')")
        self.c.execute("CREATE TABLE reports(id TEXT,user_id INTEGER,created INTEGER)")
        subscriptions.setup(self.c)
        btc.setup(self.c)
        self.c.execute("""INSERT INTO btcpay_orders(order_id,user_id,invoice_id,status,created_at)
                          VALUES ('order-1',1,'invoice-1','pending',1)""")
        self.c.commit()

    def tearDown(self):
        self.c.close()

    def invoice(self, **changes):
        result={'id':'invoice-1','metadata':{'orderId':'order-1'},
                'status':'Settled','amount':btc.PRICE,'currency':'USD'}
        result.update(changes)
        return result

    def test_verified_settlement_activates_without_manual_admin(self):
        with patch.object(btc,'request',return_value=self.invoice()):
            self.assertTrue(btc.reconcile(self.c,1))
            self.assertEqual(subscriptions.entitlement(self.c,1)['plan'],'pro')
            end=subscriptions.entitlement(self.c,1)['end']
            self.assertFalse(btc.reconcile(self.c,1))
            self.assertEqual(subscriptions.entitlement(self.c,1)['end'],end)

    def test_unsettled_payment_never_activates(self):
        with patch.object(btc,'request',return_value=self.invoice(status='Processing')):
            self.assertFalse(btc.reconcile(self.c,1))
        self.assertEqual(subscriptions.entitlement(self.c,1)['plan'],'demo')

    def test_wrong_order_reference_never_activates(self):
        with patch.object(btc,'request',return_value=self.invoice(metadata={'orderId':'other'})):
            self.assertFalse(btc.reconcile(self.c,1))
        self.assertEqual(subscriptions.entitlement(self.c,1)['plan'],'demo')

    def test_wrong_amount_never_activates(self):
        with patch.object(btc,'request',return_value=self.invoice(amount='0.01')):
            self.assertFalse(btc.reconcile(self.c,1))
        self.assertEqual(subscriptions.entitlement(self.c,1)['plan'],'demo')

    def test_other_user_cannot_reconcile_invoice(self):
        self.c.execute("INSERT INTO users VALUES(2,'other@example.com')")
        with patch.object(btc,'request',return_value=self.invoice()) as request:
            self.assertFalse(btc.reconcile(self.c,2))
            request.assert_not_called()
        self.assertEqual(subscriptions.entitlement(self.c,2)['plan'],'demo')

    def test_expired_invoice_does_not_activate(self):
        with patch.object(btc,'request',return_value=self.invoice(status='Expired')):
            self.assertFalse(btc.reconcile(self.c,1))
        self.assertEqual(subscriptions.entitlement(self.c,1)['plan'],'demo')

if __name__ == '__main__':
    unittest.main()
