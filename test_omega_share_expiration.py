import unittest
from unittest.mock import Mock, patch
import demo_shares

class ShareExpirationTests(unittest.TestCase):
    def test_lookup_enforces_expiration_independently_of_cleanup(self):
        conn = Mock()
        conn.execute.return_value.fetchone.return_value = None
        with patch.object(demo_shares, 'setup'), patch.object(demo_shares.time, 'time', return_value=123):
            self.assertIsNone(demo_shares.get(conn, 'token'))
        sql, params = conn.execute.call_args.args
        self.assertIn('expires>?', sql)
        self.assertEqual(params, ('token', 123))
