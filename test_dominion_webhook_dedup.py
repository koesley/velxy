import json
import sqlite3
import unittest
from unittest.mock import patch
import stripe_checkout as stripe

class WebhookDedupTests(unittest.TestCase):
    def test_duplicate_insert_during_reconciliation(self):
        with sqlite3.connect(':memory:') as conn:
            conn.execute('CREATE TABLE users(id INTEGER PRIMARY KEY)')
            stripe.setup(conn)
            conn.execute("INSERT INTO stripe_orders(order_id,user_id,session_id,created_at) VALUES ('o',1,'s',0)")
            body = json.dumps({'type':'checkout.session.completed','data':{'object':{'id':'s'}}}).encode()
            def reconcile(*args, **kwargs):
                import hashlib
                conn.execute("INSERT INTO stripe_webhook_events VALUES (?,?,?,?)",
                             (hashlib.sha256(body).hexdigest(),'s','checkout.session.completed',0))
            with patch.object(stripe,'verify_webhook_signature',return_value=True), patch.object(stripe,'webhook_configured',return_value=True), patch.object(stripe,'reconcile',side_effect=reconcile):
                self.assertEqual(stripe.handle_webhook(conn,body,'signature')[0],200)
            self.assertEqual(conn.execute('SELECT count(*) FROM stripe_webhook_events').fetchone()[0],1)
