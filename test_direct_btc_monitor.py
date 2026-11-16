import sqlite3
import unittest
from unittest.mock import patch
import direct_btc_orders as orders
import direct_btc_billing as billing
import direct_btc_monitor as monitor
import subscriptions

TXID = "a"*64
ADDRESS = "bc1q" + "a"*38

class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, email TEXT)")
        self.db.execute("INSERT INTO users VALUES(1,'buyer@example.com')")
        subscriptions.setup(self.db)
        with patch.object(orders, "receive_address", return_value=ADDRESS):
            self.order = orders.allocate_sqlite(self.db, 1, "wallet", "public")
        billing.quote_order(self.db, self.order["order_id"], 1, rate="100000", now=1000)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def fetch(self, path):
        if path.startswith("/address/"):
            return [{"txid": TXID, "vout": [{"scriptpubkey_address": ADDRESS, "value": 49000}]}]
        if path == "/blocks/tip/height":
            return 102
        if path == "/tx/" + TXID:
            return {"txid": TXID, "status": {"confirmed": True, "block_height": 100,
                    "block_time": 2000}, "vout": [{"scriptpubkey_address": ADDRESS, "value": 49000}]}
        raise AssertionError(path)

    def settle(self):
        return billing.settle_verified_output(self.db, self.order["order_id"], 1,
                                               TXID, 0, verified_at=2100, fetch=self.fetch)

    def test_observed_on_time_activates_once(self):
        self.assertEqual(monitor.observe_order(self.db,self.order["order_id"],1,
                                               now=1200,fetch=self.fetch),1)
        self.assertTrue(self.settle())
        self.db.commit()
        self.assertEqual(subscriptions.entitlement(self.db,1,2100)["plan"],"pro")
        self.assertFalse(self.settle())

    def test_unobserved_or_late_fails_closed(self):
        self.assertFalse(self.settle())
        self.assertEqual(monitor.observe_order(self.db,self.order["order_id"],1,
                                               now=1901,fetch=self.fetch),0)
        self.assertFalse(self.settle())

    def test_duplicate_observation_and_underpayment(self):
        self.assertEqual(monitor.observe_order(self.db,self.order["order_id"],1,
                                               now=1200,fetch=self.fetch),1)
        self.assertEqual(monitor.observe_order(self.db,self.order["order_id"],1,
                                               now=1300,fetch=self.fetch),0)
        def underpaid(path):
            value = self.fetch(path)
            if path.startswith("/tx/"):
                value["vout"][0]["value"] = 48999
            return value
        self.assertFalse(billing.settle_verified_output(self.db,self.order["order_id"],1,
                        TXID,0,verified_at=2100,fetch=underpaid))

if __name__ == "__main__":
    unittest.main()
