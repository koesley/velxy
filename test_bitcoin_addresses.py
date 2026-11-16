"""Address derivation tests using a synthetic PUBLIC account key only."""
import hashlib
import unittest
import bitcoin_addresses as b

def sample_zpub():
    # Public generator point, arbitrary public chain code; no private wallet data.
    payload = (b.ZPUB + bytes([3]) + bytes(4) + (0x80000000).to_bytes(4, "big")
               + bytes(32) + bytes(range(32)) + b._compress(b.G))
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    n = int.from_bytes(payload + checksum, "big")
    chars = ""
    while n:
        n, remainder = divmod(n, 58)
        chars = b.ALPHABET[remainder] + chars
    return chars

class AddressTests(unittest.TestCase):
    def test_distinct_deterministic_receiving_addresses(self):
        zpub = sample_zpub()
        first = b.receive_address(zpub, 0)
        second = b.receive_address(zpub, 1)
        self.assertEqual(first, b.receive_address(zpub, 0))
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("bc1q"))
        self.assertEqual(len(first), 42)
        self.assertEqual(b._polymod([3,3,0,2,3] + [b.BECH32.index(c) for c in first[3:]]), 1)

    def test_rejects_private_and_incompatible_keys(self):
        for value in ("xprv-secret", "xpub-not-bip84", "", None):
            with self.assertRaises(ValueError):
                b.receive_address(value, 0)

    def test_rejects_tampering_and_invalid_index(self):
        zpub = sample_zpub()
        with self.assertRaises(ValueError):
            b.receive_address(zpub[:-1] + ("1" if zpub[-1] != "1" else "2"), 0)
        for index in (-1, 0x80000000, True, 1.5):
            with self.assertRaises(ValueError):
                b.receive_address(zpub, index)

if __name__ == "__main__":
    unittest.main()
