"""Tests for email delivery: the notifications outbox (PRO confirmation,
renewal reminders), password reset, the SMTP send path (mocked), and the
SendGrid HTTPS API path (mocked).
Run with: python -m unittest test_email_delivery -v
"""
import http.client
import json
import os
import re
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.parse
from http.server import ThreadingHTTPServer
from unittest.mock import patch, MagicMock

import notifications
import password_reset
import subscriptions

_TMP = None
_ENV = None
_USER_N = [0]

SMTP_ENV = {
    'VELXTRIA_SMTP_HOST': 'smtp.gmail.com',
    'VELXTRIA_SMTP_PORT': '587',
    'VELXTRIA_SMTP_FROM': 'vincenthalay2005@gmail.com',
    'VELXTRIA_SMTP_USER': 'vincenthalay2005@gmail.com',
    'VELXTRIA_SMTP_PASSWORD': 'app-password-16',
}

SENDGRID_ENV = {
    'VELXTRIA_SENDGRID_API_KEY': 'SG.test-key',
    'VELXTRIA_SMTP_FROM': 'vincenthalay2005@gmail.com',
}

BREVO_ENV = {
    'VELXTRIA_BREVO_API_KEY': 'xkeysib-test-key',
    'VELXTRIA_SMTP_FROM': 'vincenthalay2005@gmail.com',
}

MAINNET_ENV = {
    'VELXTRIA_BTCPAY_MAINNET_URL': 'https://btcpay.example.com',
    'VELXTRIA_BTCPAY_MAINNET_STORE_ID': 'store123',
    'VELXTRIA_BTCPAY_MAINNET_API_KEY': 'api-key-123',
    'VELXTRIA_BTCPAY_MAINNET_WEBHOOK_SECRET': 'whsec-123',
    'VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT': '1',
}


def settled_invoice(invoice_id, order_id):
    return {
        'id': invoice_id, 'storeId': 'store123', 'amount': '49.00',
        'currency': 'USD', 'status': 'Settled',
        'metadata': {'orderId': order_id,
                     'itemDesc': 'VELXTRIA PRO - 30 Days - 50 Reports'},
        'checkoutLink': 'https://btcpay.example.com/i/' + invoice_id,
    }


class NotificationUnitTests(unittest.TestCase):
    def setUp(self):
        # A Brevo or SendGrid key in the ambient environment would flip
        # every SMTP-path test to an API path; keep them absent by default.
        os.environ.pop('VELXTRIA_BREVO_API_KEY', None)
        os.environ.pop('VELXTRIA_SENDGRID_API_KEY', None)
        self.conn = sqlite3.connect(':memory:')
        self.conn.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL)')
        self.conn.execute("INSERT INTO users(id,email) VALUES (1,'a@example.test')")
        self.conn.execute("INSERT INTO users(id,email) VALUES (2,'b@example.test')")
        notifications.setup(self.conn)
        subscriptions.setup(self.conn)

    def test_queue_dedupes(self):
        self.assertTrue(notifications.queue(
            self.conn, 'a@example.test', 'Hi', 'Body', 'test',
            dedupe_key='k1', user_id=1))
        self.assertFalse(notifications.queue(
            self.conn, 'a@example.test', 'Hi', 'Body', 'test',
            dedupe_key='k1', user_id=1))
        self.assertEqual(
            self.conn.execute("SELECT count(*) FROM email_outbox").fetchone()[0], 1)

    def test_send_mail_uses_configured_smtp(self):
        with patch.dict(os.environ, SMTP_ENV):
            mock_smtp = MagicMock()
            mock_ctx = MagicMock()
            mock_ctx.__enter__.return_value = mock_smtp
            with patch('smtplib.SMTP', return_value=mock_ctx):
                notifications.send_mail('a@example.test', 'Subject', 'Body')
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with(
            'vincenthalay2005@gmail.com', 'app-password-16')
        sent = mock_smtp.send_message.call_args[0][0]
        self.assertEqual(sent['To'], 'a@example.test')
        self.assertEqual(sent['Subject'], 'Subject')
        self.assertIn('Body', sent.get_content())

    def test_process_one_sends_and_marks_sent(self):
        notifications.queue(self.conn, 'a@example.test', 'Hi', 'Body', 'test',
                            user_id=1)
        with patch.dict(os.environ, SMTP_ENV):
            with patch('smtplib.SMTP') as mock_smtp_cls:
                mock_ctx = MagicMock()
                mock_smtp_cls.return_value = mock_ctx
                self.assertTrue(notifications.process_one(self.conn))
        self.assertEqual(
            self.conn.execute("SELECT status FROM email_outbox").fetchone()[0],
            'sent')
        self.assertFalse(notifications.process_one(self.conn))

    def test_process_one_retries_on_failure(self):
        notifications.queue(self.conn, 'a@example.test', 'Hi', 'Body', 'test',
                            user_id=1)
        with patch.dict(os.environ, SMTP_ENV):
            with patch('smtplib.SMTP', side_effect=RuntimeError('down')):
                with self.assertRaises(RuntimeError):
                    notifications.process_one(self.conn)
        row = self.conn.execute(
            "SELECT status,attempts,last_error FROM email_outbox").fetchone()
        self.assertEqual(row, ('retry', 1, 'down'))

    def test_process_one_failure_survives_caller_rollback(self):
        """A failed send keeps its retry/backoff row even when the caller
        rolls back. The delivery worker runs process_one inside a
        transaction that rolls back on the re-raised error; without an
        explicit commit in process_one the retry UPDATE is undone, the
        row stays 'queued' with 0 attempts, and the worker retries it
        every loop instead of backing off."""
        notifications.queue(self.conn, 'a@example.test', 'Hi', 'Body', 'test',
                            user_id=1)
        with patch.dict(os.environ, SMTP_ENV):
            with patch('smtplib.SMTP', side_effect=RuntimeError('down')):
                # Simulate the delivery worker: process_one runs inside a
                # transaction that rolls back when the error re-raises.
                try:
                    with self.conn:
                        notifications.process_one(self.conn)
                except RuntimeError:
                    pass
        row = self.conn.execute(
            "SELECT status,attempts,last_error FROM email_outbox").fetchone()
        self.assertEqual(row, ('retry', 1, 'down'))

    def _sendgrid_response(self):
        mock_resp = MagicMock()
        mock_resp.status = 202
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = mock_resp
        return mock_ctx

    def test_send_mail_prefers_sendgrid_over_smtp(self):
        notifications.queue(self.conn, 'a@example.test', 'Hi', 'Body', 'test',
                            user_id=1)
        env = dict(SMTP_ENV)
        env.update(SENDGRID_ENV)
        with patch.dict(os.environ, env, clear=True):
            with patch('urllib.request.urlopen',
                       return_value=self._sendgrid_response()) as mock_open:
                with patch('smtplib.SMTP') as mock_smtp_cls:
                    self.assertTrue(notifications.process_one(self.conn))
        mock_smtp_cls.assert_not_called()
        req = mock_open.call_args[0][0]
        self.assertEqual(req.full_url, notifications.SENDGRID_API_URL)
        self.assertEqual(req.get_header('Authorization'), 'Bearer SG.test-key')
        payload = json.loads(req.data.decode('utf-8'))
        self.assertEqual(payload['from']['email'],
                         'vincenthalay2005@gmail.com')
        self.assertEqual(payload['personalizations'][0]['to'][0]['email'],
                         'a@example.test')
        self.assertEqual(payload['subject'], 'Hi')
        self.assertEqual(payload['content'][0]['value'], 'Body')
        self.assertEqual(
            self.conn.execute("SELECT status FROM email_outbox").fetchone()[0],
            'sent')

    def test_send_mail_sendgrid_attachment(self):
        import base64
        with patch.dict(os.environ, SENDGRID_ENV, clear=True):
            with patch('urllib.request.urlopen',
                       return_value=self._sendgrid_response()) as mock_open:
                notifications.send_mail(
                    'a@example.test', 'Report', 'Attached',
                    attachment=('VELXTRIA_Report.zip', b'ZIPBYTES',
                                'application/zip'))
        payload = json.loads(mock_open.call_args[0][0].data.decode('utf-8'))
        att = payload['attachments'][0]
        self.assertEqual(att['filename'], 'VELXTRIA_Report.zip')
        self.assertEqual(att['type'], 'application/zip')
        self.assertEqual(base64.b64decode(att['content']), b'ZIPBYTES')

    def test_send_mail_sendgrid_error_retries(self):
        import urllib.error
        notifications.queue(self.conn, 'a@example.test', 'Hi', 'Body', 'test',
                            user_id=1)
        err = urllib.error.HTTPError(
            notifications.SENDGRID_API_URL, 401, 'Unauthorized', {}, None)
        with patch.dict(os.environ, SENDGRID_ENV, clear=True):
            with patch('urllib.request.urlopen', side_effect=err):
                with self.assertRaises(RuntimeError) as ctx:
                    notifications.process_one(self.conn)
        self.assertIn('SendGrid 401', str(ctx.exception))
        row = self.conn.execute(
            "SELECT status,attempts,last_error FROM email_outbox").fetchone()
        self.assertEqual(row[0], 'retry')
        self.assertEqual(row[1], 1)
        self.assertIn('SendGrid 401', row[2])

    def _brevo_response(self):
        mock_resp = MagicMock()
        mock_resp.status = 201
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = mock_resp
        return mock_ctx

    def test_send_mail_prefers_brevo_over_sendgrid_and_smtp(self):
        notifications.queue(self.conn, 'a@example.test', 'Hi', 'Body', 'test',
                            user_id=1)
        env = dict(SMTP_ENV)
        env.update(SENDGRID_ENV)
        env.update(BREVO_ENV)
        with patch.dict(os.environ, env, clear=True):
            with patch('urllib.request.urlopen',
                       return_value=self._brevo_response()) as mock_open:
                with patch('smtplib.SMTP') as mock_smtp_cls:
                    self.assertTrue(notifications.process_one(self.conn))
        mock_smtp_cls.assert_not_called()
        req = mock_open.call_args[0][0]
        self.assertEqual(req.full_url, notifications.BREVO_API_URL)
        self.assertEqual(req.get_header('Api-key'), 'xkeysib-test-key')
        payload = json.loads(req.data.decode('utf-8'))
        self.assertEqual(payload['sender']['email'],
                         'vincenthalay2005@gmail.com')
        self.assertEqual(payload['to'][0]['email'], 'a@example.test')
        self.assertEqual(payload['subject'], 'Hi')
        self.assertEqual(payload['textContent'], 'Body')
        self.assertEqual(
            self.conn.execute("SELECT status FROM email_outbox").fetchone()[0],
            'sent')

    def test_send_mail_brevo_attachment(self):
        import base64
        with patch.dict(os.environ, BREVO_ENV, clear=True):
            with patch('urllib.request.urlopen',
                       return_value=self._brevo_response()) as mock_open:
                notifications.send_mail(
                    'a@example.test', 'Report', 'Attached',
                    attachment=('VELXTRIA_Report.zip', b'ZIPBYTES',
                                'application/zip'))
        payload = json.loads(mock_open.call_args[0][0].data.decode('utf-8'))
        att = payload['attachment'][0]
        self.assertEqual(att['name'], 'VELXTRIA_Report.zip')
        self.assertEqual(base64.b64decode(att['content']), b'ZIPBYTES')

    def test_send_mail_brevo_error_retries(self):
        import urllib.error
        notifications.queue(self.conn, 'a@example.test', 'Hi', 'Body', 'test',
                            user_id=1)
        err = urllib.error.HTTPError(
            notifications.BREVO_API_URL, 401, 'Unauthorized', {}, None)
        with patch.dict(os.environ, BREVO_ENV, clear=True):
            with patch('urllib.request.urlopen', side_effect=err):
                with self.assertRaises(RuntimeError) as ctx:
                    notifications.process_one(self.conn)
        self.assertIn('Brevo 401', str(ctx.exception))
        row = self.conn.execute(
            "SELECT status,attempts,last_error FROM email_outbox").fetchone()
        self.assertEqual(row[0], 'retry')
        self.assertEqual(row[1], 1)
        self.assertIn('Brevo 401', row[2])

    def test_send_mail_falls_back_to_sendgrid_without_brevo_key(self):
        notifications.queue(self.conn, 'a@example.test', 'Hi', 'Body', 'test',
                            user_id=1)
        env = dict(SMTP_ENV)
        env.update(SENDGRID_ENV)
        with patch.dict(os.environ, env, clear=True):
            with patch('urllib.request.urlopen',
                       return_value=self._sendgrid_response()) as mock_open:
                with patch('smtplib.SMTP') as mock_smtp_cls:
                    self.assertTrue(notifications.process_one(self.conn))
        mock_smtp_cls.assert_not_called()
        req = mock_open.call_args[0][0]
        self.assertEqual(req.full_url, notifications.SENDGRID_API_URL)
        self.assertEqual(req.get_header('Authorization'), 'Bearer SG.test-key')

    def test_send_mail_falls_back_to_smtp_without_key(self):
        notifications.queue(self.conn, 'a@example.test', 'Hi', 'Body', 'test',
                            user_id=1)
        with patch.dict(os.environ, SMTP_ENV, clear=True):
            with patch('urllib.request.urlopen') as mock_open:
                with patch('smtplib.SMTP') as mock_smtp_cls:
                    mock_ctx = MagicMock()
                    mock_smtp_cls.return_value = mock_ctx
                    self.assertTrue(notifications.process_one(self.conn))
        mock_open.assert_not_called()
        mock_smtp_cls.assert_called_once()

    def test_email_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(notifications.email_configured())
        with patch.dict(os.environ, {'VELXTRIA_SMTP_HOST': 'smtp.gmail.com'},
                        clear=True):
            self.assertTrue(notifications.email_configured())
            self.assertTrue(notifications.smtp_configured())
            self.assertFalse(notifications.sendgrid_configured())
        with patch.dict(os.environ, {'VELXTRIA_SENDGRID_API_KEY': 'SG.x'},
                        clear=True):
            self.assertTrue(notifications.email_configured())
            self.assertFalse(notifications.smtp_configured())
            self.assertTrue(notifications.sendgrid_configured())
            self.assertFalse(notifications.brevo_configured())
        with patch.dict(os.environ, {'VELXTRIA_BREVO_API_KEY': 'xkeysib-x'},
                        clear=True):
            self.assertTrue(notifications.email_configured())
            self.assertFalse(notifications.smtp_configured())
            self.assertFalse(notifications.sendgrid_configured())
            self.assertTrue(notifications.brevo_configured())

    def test_renewal_reminder_scan(self):
        now = int(time.time())
        with self.conn:
            self.conn.execute(
                'INSERT INTO subscriptions'
                '(user_id,product_key,pricing_plan,status,source_reference,'
                'period_start,period_end,verified_at,verification_source,updated_at)'
                ' VALUES (?,?,?,?,?,?,?,?,?,?)',
                (1, subscriptions.PRODUCT_KEY, subscriptions.PRICING_PLAN,
                 'active', 'inv1', now - 100, now + 2 * 86400, now, 'test', now))
            self.conn.execute(
                'INSERT INTO subscriptions'
                '(user_id,product_key,pricing_plan,status,source_reference,'
                'period_start,period_end,verified_at,verification_source,updated_at)'
                ' VALUES (?,?,?,?,?,?,?,?,?,?)',
                (2, subscriptions.PRODUCT_KEY, subscriptions.PRICING_PLAN,
                 'active', 'inv2', now - 100, now + 10 * 86400, now, 'test', now))
        self.assertEqual(notifications.scan_renewal_reminders(self.conn, now), 1)
        self.assertEqual(notifications.scan_renewal_reminders(self.conn, now), 0)
        row = self.conn.execute(
            "SELECT recipient,kind FROM email_outbox").fetchone()
        self.assertEqual(row, ('a@example.test', 'renewal_reminder'))

    def test_pro_confirmation_queues_once(self):
        now = int(time.time())
        self.assertTrue(notifications.queue_pro_confirmation(
            self.conn, 1, 'a@example.test', now + 30 * 86400, 'vx-1'))
        self.assertFalse(notifications.queue_pro_confirmation(
            self.conn, 1, 'a@example.test', now + 30 * 86400, 'vx-1'))

    def test_reclaim_stale_returns_abandoned_row_to_retry(self):
        notifications.queue(self.conn, 'a@example.test', 'Hi', 'Body', 'test',
                            user_id=1)
        now = int(time.time())
        with self.conn:
            self.conn.execute(
                "UPDATE email_outbox SET status='sending', attempts=1,"
                " next_attempt=?", (now - 600,))
        self.assertEqual(notifications.reclaim_stale(self.conn, now=now), 1)
        row = self.conn.execute(
            "SELECT status,attempts FROM email_outbox").fetchone()
        self.assertEqual(row, ('retry', 1))
        with patch.dict(os.environ, SMTP_ENV):
            with patch('smtplib.SMTP') as mock_smtp_cls:
                mock_smtp_cls.return_value = MagicMock()
                self.assertTrue(notifications.process_one(self.conn))
        self.assertEqual(
            self.conn.execute("SELECT status FROM email_outbox").fetchone()[0],
            'sent')

    def test_reclaim_stale_ignores_fresh_sending_row(self):
        notifications.queue(self.conn, 'a@example.test', 'Hi', 'Body', 'test',
                            user_id=1)
        now = int(time.time())
        with self.conn:
            self.conn.execute(
                "UPDATE email_outbox SET status='sending', attempts=1,"
                " next_attempt=?", (now,))
        self.assertEqual(notifications.reclaim_stale(self.conn, now=now), 0)
        row = self.conn.execute(
            "SELECT status FROM email_outbox").fetchone()
        self.assertEqual(row, ('sending',))

    def test_reclaim_stale_marks_exhausted_row_failed(self):
        notifications.queue(self.conn, 'a@example.test', 'Hi', 'Body', 'test',
                            user_id=1)
        now = int(time.time())
        with self.conn:
            self.conn.execute(
                "UPDATE email_outbox SET status='sending', attempts=3,"
                " next_attempt=?", (now - 600,))
        self.assertEqual(notifications.reclaim_stale(self.conn, now=now), 1)
        row = self.conn.execute(
            "SELECT status,attempts FROM email_outbox").fetchone()
        self.assertEqual(row, ('failed', 3))
        self.assertFalse(notifications.process_one(self.conn))


def setUpModule():
    global _TMP, _ENV
    _TMP = tempfile.TemporaryDirectory()
    _ENV = patch.dict(os.environ, {
        'VELXTRIA_DATA_DIR': _TMP.name,
        'VELXTRIA_DEPLOYMENT_MODE': 'local',
    })
    _ENV.start()
    import portal  # noqa: F401
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


def tearDownModule():
    import portal
    with portal.db() as c:
        c.execute(
            "DELETE FROM email_outbox WHERE recipient LIKE 'em%@example.test'")
        c.execute(
            "DELETE FROM password_resets WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE 'em%@example.test')")
        c.execute(
            'DELETE FROM referral_rewards WHERE referrer_id IN '
            "(SELECT id FROM users WHERE email LIKE 'em%@example.test')")
        c.execute(
            'DELETE FROM referral_signups WHERE referrer_id IN '
            "(SELECT id FROM users WHERE email LIKE 'em%@example.test')")
        c.execute(
            "DELETE FROM referrals WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE 'em%@example.test')")
        c.execute(
            'DELETE FROM reports WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'em%@example.test')")
        c.execute(
            'DELETE FROM sessions WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'em%@example.test')")
        c.execute(
            "DELETE FROM btcpay_orders WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE 'em%@example.test')")
        c.execute(
            'DELETE FROM subscriptions WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'em%@example.test')")
        c.execute("DELETE FROM users WHERE email LIKE 'em%@example.test'")
    _ENV.stop()
    _TMP.cleanup()
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class EmailFlowTests(unittest.TestCase):
    def setUp(self):
        # Keep the no-email-config test deterministic: a Brevo or SendGrid
        # key in the ambient environment would make /forgot offer email.
        os.environ.pop('VELXTRIA_BREVO_API_KEY', None)
        os.environ.pop('VELXTRIA_SENDGRID_API_KEY', None)
        import portal
        self.portal = portal
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), portal.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.port = self.server.server_address[1]

    def request(self, method, path, body=b'', content_type=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
        try:
            all_headers = dict(headers or {})
            if content_type:
                all_headers['Content-Type'] = content_type
            conn.request(method, path, body=body, headers=all_headers)
            resp = conn.getresponse()
            return (resp.status, dict(resp.headers), resp.read())
        finally:
            conn.close()

    def get(self, path, cookie=None):
        headers = {'Cookie': cookie} if cookie else None
        status, headers_out, body = self.request('GET', path, headers=headers)
        return status, headers_out, body.decode('utf-8', 'replace')

    def post_form(self, path, fields, cookie=None):
        body = urllib.parse.urlencode(fields).encode()
        headers = {'Cookie': cookie} if cookie else None
        status, headers_out, raw = self.request(
            'POST', path, body=body,
            content_type='application/x-www-form-urlencoded',
            headers=headers)
        return status, headers_out, raw.decode('utf-8', 'replace')

    def sign_in(self, email):
        data = {'email': email, 'password': 'TestPass123456!'}
        status, headers, _ = self.post_form('/register', data)
        self.assertEqual(status, 303)
        status, headers, _ = self.post_form('/login', data)
        self.assertEqual(status, 303)
        match = re.search(r'velxtria_session=([^;]+)', headers.get('Set-Cookie', ''))
        self.assertTrue(match, 'login did not set a session cookie')
        return 'velxtria_session=' + match.group(1)

    def new_user(self):
        _USER_N[0] += 1
        email = 'em%d@example.test' % _USER_N[0]
        return email, self.sign_in(email)

    def user_id(self, email):
        with self.portal.db() as c:
            return c.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()[0]

    def outbox_for(self, email):
        with self.portal.db() as c:
            return c.execute(
                'SELECT subject,body,kind FROM email_outbox WHERE recipient=?',
                (email,)).fetchall()

    def test_pro_confirmation_queued_on_settlement(self):
        import btcpay_mainnet
        email, _ = self.new_user()
        uid = self.user_id(email)

        def fake(method, path, payload=None):
            if method == 'GET' and path == '/invoices/inv1':
                return settled_invoice('inv1', order_id)
            raise RuntimeError('unexpected fake call %s %s' % (method, path))

        with patch.dict(os.environ, MAINNET_ENV):
            with self.portal.db() as c:
                order_id = btcpay_mainnet.create_order(c, uid)
                c.execute("UPDATE btcpay_orders SET invoice_id=?,checkout_url=?,"
                          "status='pending' WHERE order_id=?",
                          ('inv1', 'https://btcpay.example.com/i/inv1', order_id))
            with self.portal.db() as c:
                self.assertTrue(btcpay_mainnet.reconcile(c, uid, req=fake))
        rows = self.outbox_for(email)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], 'pro_activated')
        self.assertIn('PRO is active', rows[0][0])

    def test_forgot_password_flow(self):
        email, cookie = self.new_user()
        with patch.dict(os.environ, SMTP_ENV):
            status, _, body = self.post_form('/forgot', {'email': email})
        self.assertEqual(status, 200)
        self.assertIn('Check your email', body)
        rows = self.outbox_for(email)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], 'password_reset')
        match = re.search(r'/reset\?token=([A-Za-z0-9_-]+)', rows[0][1])
        self.assertTrue(match, 'reset email has no link')
        token = match.group(1)

        status, _, body = self.get('/reset?token=' + token)
        self.assertEqual(status, 200)
        self.assertIn('Choose a new password', body)

        status, headers, _ = self.post_form(
            '/reset', {'token': token, 'password': 'NewTestPass123456!'})
        self.assertEqual(status, 303)
        self.assertIn('/login?reset=1', headers.get('Location', ''))

        # The token is single-use.
        status, _, _ = self.post_form(
            '/reset', {'token': token, 'password': 'AnotherPass123456!'})
        self.assertEqual(status, 400)

        # The new password signs in; the old one does not.
        status, _, _ = self.post_form(
            '/login', {'email': email, 'password': 'NewTestPass123456!'})
        self.assertEqual(status, 303)
        status, _, _ = self.post_form(
            '/login', {'email': email, 'password': 'TestPass123456!'})
        self.assertEqual(status, 401)

        status, _, body = self.get('/login?reset=1')
        self.assertIn('Password updated', body)

    def test_forgot_unknown_email_reveals_nothing(self):
        with patch.dict(os.environ, SMTP_ENV):
            status, _, body = self.post_form(
                '/forgot', {'email': 'nobody@example.test'})
        self.assertEqual(status, 200)
        self.assertIn('Check your email', body)
        self.assertEqual(self.outbox_for('nobody@example.test'), [])

    def test_forgot_without_smtp_promises_nothing(self):
        email, _ = self.new_user()
        status, _, body = self.post_form('/forgot', {'email': email})
        self.assertEqual(status, 200)
        self.assertIn('not available yet', body)
        self.assertEqual(self.outbox_for(email), [])

    def test_reset_link_expired(self):
        email, _ = self.new_user()
        with patch.dict(os.environ, SMTP_ENV):
            self.post_form('/forgot', {'email': email})
        rows = self.outbox_for(email)
        token = re.search(r'/reset\?token=([A-Za-z0-9_-]+)', rows[0][1]).group(1)
        with self.portal.db() as c:
            c.execute('UPDATE password_resets SET expires=? WHERE user_id=?',
                      (int(time.time()) - 1, self.user_id(email)))
        status, _, body = self.get('/reset?token=' + token)
        self.assertEqual(status, 400)
        self.assertIn('Link expired', body)


if __name__ == '__main__':
    unittest.main()
