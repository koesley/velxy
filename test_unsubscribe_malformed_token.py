import sqlite3
import unittest

import email_unsubscribe as unsubscribe


class MalformedTokenTests(unittest.TestCase):
    def test_invalid_tokens_do_not_raise_or_suppress(self):
        with sqlite3.connect(':memory:') as conn:
            email = 'customer@example.com'
            valid = unsubscribe.get_or_create_token(conn, email)
            for token in ('é', '🔒', '', None, b'bad', 'wrong'):
                with self.subTest(token=token):
                    self.assertFalse(unsubscribe.record_unsubscribe(conn, email, token))
                    self.assertFalse(unsubscribe.is_unsubscribed(conn, email))
            self.assertTrue(unsubscribe.record_unsubscribe(conn, email, valid))
            self.assertTrue(unsubscribe.is_unsubscribed(conn, email))
            self.assertTrue(unsubscribe.record_unsubscribe(conn, email, valid))
