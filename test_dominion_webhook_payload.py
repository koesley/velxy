import json
import unittest
from unittest.mock import Mock, patch
import stripe_checkout as stripe

class WebhookPayloadTests(unittest.TestCase):
    def test_malformed_fields_do_not_reach_database(self):
        for event, session in [([], 's'), ({}, 's'), ('checkout.session.completed', []), ('checkout.session.completed', {'id':'s'}), ('checkout.session.completed', ' '), ('unknown', 's')]:
            with self.subTest(event=event, session=session):
                conn = Mock()
                body = json.dumps({'type':event,'data':{'object':{'id':session}}}).encode()
                with patch.object(stripe,'verify_webhook_signature',return_value=True), patch.object(stripe,'webhook_configured',return_value=True):
                    self.assertEqual(stripe.handle_webhook(conn,body,'signature')[0],200)
                conn.execute.assert_not_called()
