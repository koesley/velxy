import unittest
from unittest.mock import patch
import verify_database

class FakeConnection:
    def __init__(self, result=(1,)):
        self.result = result
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, query):
        assert query == "SELECT 1"
        return self
    def fetchone(self):
        return self.result

class DatabaseProbeTests(unittest.TestCase):
    def test_success(self):
        with patch("persistent.REMOTE", True):
            self.assertEqual(verify_database.check(lambda: FakeConnection()), "connected")
    def test_wrong_result_fails_closed(self):
        with patch("persistent.REMOTE", True):
            self.assertEqual(verify_database.check(lambda: FakeConnection((0,))), "failed")
    def test_connection_failure_fails_closed(self):
        with patch("persistent.REMOTE", True):
            def broken():
                raise RuntimeError("secret connection string")
            self.assertEqual(verify_database.check(broken), "failed")
    def test_unconfigured(self):
        with patch("persistent.REMOTE", False):
            self.assertEqual(verify_database.check(lambda: FakeConnection()), "not_configured")

if __name__ == "__main__":
    unittest.main()
