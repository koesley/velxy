import unittest
from unittest.mock import patch
import verify_btc_wallet as wallet

ADDRESS = "bc1qxdjxk3kzke0shnlqupkndyel7mf9v6fahfkgx4"

class WalletVerificationTests(unittest.TestCase):
    def test_match_at_nonzero_index(self):
        with patch.object(wallet, "receive_address", side_effect=lambda key, i: ADDRESS if i == 4 else "other"):
            self.assertEqual(wallet.find_address("watch-only-key", ADDRESS, 10), 4)

    def test_no_match_fails_closed(self):
        with patch.object(wallet, "receive_address", return_value="other"):
            self.assertIsNone(wallet.find_address("watch-only-key", ADDRESS, 10))

    def test_invalid_address_and_range(self):
        with self.assertRaises(ValueError):
            wallet.find_address("key", "not-an-address")
        with self.assertRaises(ValueError):
            wallet.find_address("key", ADDRESS, 10001)

if __name__ == "__main__":
    unittest.main()
