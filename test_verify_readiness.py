"""Readiness regression tests: both dependencies must be healthy."""
import unittest
from verify_readiness import check

class ReadinessTests(unittest.TestCase):
    def test_both_connected(self):
        self.assertTrue(check(lambda: "connected", lambda: "connected"))

    def test_database_failure(self):
        self.assertFalse(check(lambda: "failed", lambda: "connected"))

    def test_storage_failure(self):
        self.assertFalse(check(lambda: "connected", lambda: "failed"))

    def test_public_bucket_rejected(self):
        self.assertFalse(check(lambda: "connected", lambda: "unsafe_public_bucket"))

    def test_unconfigured_rejected(self):
        self.assertFalse(check(lambda: "not_configured", lambda: "connected"))

    def test_exception_fails_closed(self):
        def broken():
            raise RuntimeError("secret")
        self.assertFalse(check(broken, lambda: "connected"))
        self.assertFalse(check(lambda: "connected", broken))

    def test_storage_not_called_when_database_down(self):
        def should_not_call():
            raise AssertionError("storage should not be probed")
        self.assertFalse(check(lambda: "failed", should_not_call))

if __name__ == "__main__":
    unittest.main()
