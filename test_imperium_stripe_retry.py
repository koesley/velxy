import unittest
from unittest.mock import Mock
import stripe_checkout as stripe

class StripeRetryTests(unittest.TestCase):
    def test_unavailable_verification_retry_policy(self):
        conn = Mock()
        conn.execute.return_value.fetchall.return_value = [('order', 'session')]
        fetch = Mock(side_effect=RuntimeError('offline'))
        self.assertFalse(stripe.reconcile(conn, 1, req=fetch))
        with self.assertRaises(RuntimeError):
            stripe.reconcile(conn, 1, req=fetch, retry_unavailable=True)
