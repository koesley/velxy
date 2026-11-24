import hashlib
import hmac
import unittest
from unittest.mock import patch

import stripe_checkout as stripe


class StripeSignatureBoundaryTests(unittest.TestCase):
    def test_timestamp_and_signature_boundaries(self):
        body = b'{}'
        now = 1700000000
        secret = 'synthetic-test-secret'
        with patch.dict('os.environ', {'VELXTRIA_STRIPE_WEBHOOK_SECRET': secret}), patch.object(stripe.time, 'time', return_value=now):
            for offset in (-301, -300, 0, 300, 301):
                with self.subTest(offset=offset):
                    timestamp = now + offset
                    digest = hmac.new(secret.encode(), str(timestamp).encode() + b'.' + body, hashlib.sha256).hexdigest()
                    header = f't={timestamp},v1={digest}'
                    self.assertEqual(stripe.verify_webhook_signature(body, header), abs(offset) <= 300)
            digest = hmac.new(secret.encode(), str(now).encode() + b'.' + body, hashlib.sha256).hexdigest()
            self.assertFalse(stripe.verify_webhook_signature(body, f't={now},v1=' + 'é' * 64))
            self.assertTrue(stripe.verify_webhook_signature(body, f't={now},v1=' + 'é' * 64 + ',v1=' + digest))
            self.assertFalse(stripe.verify_webhook_signature(body, f't={now},v1=bad'))
