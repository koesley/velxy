"""Regression tests for safe outbox claims and stale-send recovery.

Run: python -m unittest test_email_outbox_claims -v
"""
import sqlite3
import unittest
from unittest.mock import patch

import notifications


class EmailOutboxClaimTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        notifications.setup(self.conn)
        notifications.queue(self.conn, 'owner@example.test', 'Subject', 'Body', 'test')

    def test_claim_marks_send_start_for_stale_recovery(self):
        with patch('notifications.time.time', return_value=2000000000):
            with patch('notifications.send_mail') as send:
                self.assertTrue(notifications.process_one(self.conn))
        send.assert_called_once_with('owner@example.test', 'Subject', 'Body')
        status, attempts, stamp = self.conn.execute(
            'SELECT status,attempts,next_attempt FROM email_outbox').fetchone()
        self.assertEqual((status, attempts, stamp), ('sent', 1, 2000000000))

    def test_stale_claim_cannot_send_after_another_worker_claims(self):
        original_execute = self.conn.execute
        class RacingConnection:
            def execute(self, sql, params=()):
                if "UPDATE email_outbox SET status='sending'" in sql:
                    original_execute("UPDATE email_outbox SET status='sending' WHERE status='queued'")
                return original_execute(sql, params)
        with patch('notifications.send_mail') as send:
            self.assertFalse(notifications.process_one(RacingConnection()))
        send.assert_not_called()
        self.assertEqual(self.conn.execute(
            'SELECT attempts FROM email_outbox').fetchone()[0], 0)

    def test_fresh_claim_not_reclaimed_until_timeout(self):
        with patch('notifications.time.time', return_value=2000000000):
            with patch('notifications.send_mail', side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    notifications.process_one(self.conn)
        self.assertEqual(notifications.reclaim_stale(
            self.conn, now=2000000299), 0)
        self.assertEqual(notifications.reclaim_stale(
            self.conn, now=2000000300), 1)
        self.assertEqual(self.conn.execute(
            'SELECT status FROM email_outbox').fetchone()[0], 'retry')

    def test_failed_send_retains_retry_backoff(self):
        with patch('notifications.time.time', return_value=2000000000):
            with patch('notifications.send_mail', side_effect=RuntimeError('offline')):
                with self.assertRaisesRegex(RuntimeError, 'offline'):
                    notifications.process_one(self.conn)
        self.assertEqual(self.conn.execute(
            'SELECT status,attempts,next_attempt FROM email_outbox').fetchone(),
            ('retry', 1, 2000000060))


if __name__ == '__main__':
    unittest.main()
