import unittest
from unittest.mock import patch

import stripe_checkout as stripe


class ExplicitEvidenceTests(unittest.TestCase):
    def test_missing_or_malformed_evidence_fails_closed(self):
        valid = dict(id='cs_example', metadata={'order_id': 'order'}, payment_status='paid', amount_total=4900, currency='usd', livemode=True)
        with patch.dict('os.environ', {'VELXTRIA_STRIPE_ALLOW_TEST_ACTIVATION': '0'}):
            self.assertTrue(stripe.verify_session(valid, 'order', 'cs_example')[0])
            for key, values in [('livemode', [None, 0, 1, 'true', False]), ('id', ['', ' ', 123, None]), ('amount_total', [4900.0, '4900', None])]:
                for value in values:
                    with self.subTest(key=key, value=value):
                        self.assertFalse(stripe.verify_session(dict(valid, **{key: value}), 'order')[0])
                missing = dict(valid)
                del missing[key]
                self.assertFalse(stripe.verify_session(missing, 'order')[0])
        with patch.dict('os.environ', {'VELXTRIA_STRIPE_ALLOW_TEST_ACTIVATION': '1'}):
            self.assertTrue(stripe.verify_session(dict(valid, livemode=False), 'order')[0])
            self.assertFalse(stripe.verify_session(dict(valid, livemode=None), 'order')[0])
