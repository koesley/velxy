import sqlite3
import unittest
from unittest.mock import patch
import direct_btc_orders as orders
import direct_btc_billing as billing
import subscriptions

class BillingTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, email TEXT)")
        self.conn.execute("INSERT INTO users VALUES(1,'buyer@example.com')")
        subscriptions.setup(self.conn)
        with patch.object(orders, "receive_address", return_value="bc1q" + "a"*38):
            self.order = orders.allocate_sqlite(self.conn, 1, "wallet", "public")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def quote(self):
        q = billing.quote_order(self.conn, self.order["order_id"], 1,
                                rate="100000", now=1000)
        self.conn.commit()
        return q

    def settle(self, **kwargs):
        return billing.settle_verified_output(
            self.conn, self.order["order_id"], 1, "a"*64, 0,
            verified_at=2000, fetch=lambda path: {}, **kwargs)

    def test_fixed_quote(self):
        quote = self.quote()
        self.assertEqual(quote["expected_sats"], 49000)
        self.assertEqual(quote["expires_at"], 1900)
        with self.assertRaises(ValueError):
            self.quote()

    def test_settlement_fails_closed_until_expiry_proof(self):
        self.quote()
        self.assertFalse(self.settle())
        self.conn.commit()
        self.assertEqual(subscriptions.entitlement(self.conn, 1, 2000)["plan"], "demo")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM direct_btc_claims").fetchone()[0], 0)
        self.assertFalse(self.settle())

    def test_no_underpayment_or_late_payment(self):
        self.quote()
        self.assertFalse(billing.settle_verified_output(
            self.conn,self.order["order_id"],1,"a"*64,0,
            verified_at=2000,fetch=lambda path: {}))
        self.assertFalse(billing.settle_verified_output(
            self.conn,self.order["order_id"],1,"a"*64,0,
            verified_at=2000,fetch=lambda path: {}))
        self.assertEqual(subscriptions.entitlement(self.conn,1,2000)["plan"],"demo")

    def test_wrong_user_cannot_activate(self):
        self.quote()
        self.assertFalse(billing.settle_verified_output(
            self.conn,self.order["order_id"],2,"a"*64,0,
            verified_at=2000,fetch=lambda path: {}))

    def test_invalid_exchange_rates(self):
        for rate in ("0", "-1", "NaN", "Infinity"):
            with self.assertRaises(ValueError):
                billing.sats_for_usd(rate)

if __name__ == "__main__":
    unittest.main()
