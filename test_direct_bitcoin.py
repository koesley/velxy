import unittest
from unittest.mock import patch
import direct_bitcoin as btc

ADDRESS = "bc1qxdjxk3kzke0shnlqupkndyel7mf9v6fahfkgx4"
TXID = "a" * 64

def api(path):
    if path == "/blocks/tip/height":
        return 100
    if path == "/tx/" + TXID:
        return {"txid": TXID, "status": {
            "confirmed": True, "block_height": 98, "block_time": 2000},
            "vout": [{"scriptpubkey_address": ADDRESS, "value": 100000}]}
    raise AssertionError(path)

class DirectBitcoinTests(unittest.TestCase):
    def test_valid_confirmed_output(self):
        self.assertEqual(btc.verify_transaction(TXID, ADDRESS, 90000, 1000, fetch=api),
                         [(TXID, 0, 100000)])

    def test_wrong_address_and_underpayment(self):
        self.assertEqual(btc.verify_transaction(TXID, ADDRESS, 100001, 1000, fetch=api), [])
        self.assertEqual(btc.verify_transaction(TXID, "bc1qwrong", 90000, 1000, fetch=api), [])

    def test_payment_predating_order_is_rejected(self):
        self.assertEqual(btc.verify_transaction(TXID, ADDRESS, 90000, 2001, fetch=api), [])

    def test_insufficient_confirmations_are_rejected(self):
        def low_tip(path):
            return 99 if path == "/blocks/tip/height" else api(path)
        self.assertEqual(btc.verify_transaction(TXID, ADDRESS, 90000, 1000, fetch=low_tip), [])

    def test_invalid_txid_is_rejected_without_network(self):
        self.assertEqual(btc.verify_transaction("not-a-tx", ADDRESS, 90000, 1000,
                         fetch=lambda _: self.fail("network called")), [])

    def test_not_launch_enabled(self):
        self.assertFalse(btc.ready_for_launch())

if __name__ == "__main__":
    unittest.main()
