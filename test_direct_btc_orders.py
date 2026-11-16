import sqlite3
import unittest
from unittest.mock import patch
import direct_btc_orders as orders

class DirectOrderTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addresses = lambda key, index: "bc1q" + str(index).zfill(38)
        orders.setup(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def allocate(self, user=1):
        with patch.object(orders, "receive_address", side_effect=self.addresses):
            return orders.allocate_sqlite(self.conn, user, "wallet-1", "synthetic-public-key")

    def test_unique_sequential_addresses(self):
        a, b = self.allocate(), self.allocate(2)
        self.assertNotEqual(a["address"], b["address"])
        self.assertEqual((a["index"], b["index"]), (0, 1))
        self.assertNotEqual(a["order_id"], b["order_id"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM direct_btc_orders").fetchone()[0], 2)

    def test_failed_allocation_rolls_back_counter(self):
        with patch.object(orders, "receive_address", side_effect=ValueError("bad zpub")):
            with self.assertRaises(ValueError):
                orders.allocate_sqlite(self.conn, 1, "wallet-1", "bad")
        self.assertEqual(self.allocate()["index"], 0)

    def test_duplicate_output_cannot_pay_twice(self):
        a, b = self.allocate(), self.allocate(2)
        self.conn.execute("UPDATE direct_btc_orders SET status='pending'")
        self.assertTrue(orders.claim_output(self.conn, a["order_id"], "a"*64, 0))
        self.assertFalse(orders.claim_output(self.conn, b["order_id"], "a"*64, 0))
        self.assertTrue(orders.claim_output(self.conn, b["order_id"], "a"*64, 1))

    def test_unquoted_order_cannot_claim(self):
        a = self.allocate()
        self.assertFalse(orders.claim_output(self.conn, a["order_id"], "b"*64, 0))

    def test_reject_invalid_inputs(self):
        with self.assertRaises(ValueError):
            self.allocate(True)
        with self.assertRaises(ValueError):
            orders.claim_output(self.conn, "bad", "a"*64, 0)

if __name__ == "__main__":
    unittest.main()
