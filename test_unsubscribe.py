"""Tests for the marketing-email opt-out (audit finding MEDIUM-2).

The site's marketing mail — the welcome sequence, the demo-lead
follow-ups, and the PRO upsells — had no way out: no unsubscribe link
and no suppression list, so a recipient who asked to stop still got
every step. Now:

- email_unsubscribes holds one row per address: a random token and an
  unsubscribed flag. The token row is created when a marketing email is
  queued (the footer link needs a stable token), so row existence alone
  does not mean opted out — only the flag does.
- Every marketing body carries a one-click unsubscribe link.
- notifications.queue() never queues marketing mail to a suppressed
  address; process_one() never sends a queued marketing row whose
  recipient opted out after queueing — it is marked 'suppressed' and
  never retried.
- GET /unsubscribe?email=..&token=.. records the opt-out on a valid
  token and shows a confirmation; a wrong or missing token gets the
  same 404 without revealing whether the address is on file.
- Transactional mail (password resets, PRO confirmations, demo-report
  emails) is never suppressed.

Run with:
  python -m unittest test_unsubscribe -v
"""
import http.client
import os
import re
import sqlite3
import tempfile
import threading
import unittest
import urllib.parse
from http.server import ThreadingHTTPServer
from unittest.mock import patch

_TMP = None
_ENV = None

PASSWORD = 'UnsubPass123456!'

_EMAIL_N = [0]


def fresh_email():
    _EMAIL_N[0] += 1
    return 'unsub-%d@example.com' % _EMAIL_N[0]


def setUpModule():
    global _TMP, _ENV
    _TMP = tempfile.TemporaryDirectory()
    _ENV = patch.dict(os.environ, {
        'VELXTRIA_DATA_DIR': _TMP.name,
        'VELXTRIA_DEPLOYMENT_MODE': 'local',
        'VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT': '0',
    })
    _ENV.start()
    import portal  # noqa: F401
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


def tearDownModule():
    import portal
    # Remove this module's test rows, then drop the whole temp dir.
    try:
        conn = sqlite3.connect(str(portal.DB))
        try:
            conn.execute(
                "DELETE FROM users WHERE email LIKE 'unsub-%@example.com'")
            conn.execute(
                "DELETE FROM email_outbox"
                " WHERE recipient LIKE 'unsub-%@example.com'")
            conn.execute(
                "DELETE FROM email_unsubscribes"
                " WHERE email LIKE 'unsub-%@example.com'")
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass
    _ENV.stop()
    _TMP.cleanup()
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class UnsubscribeTests(unittest.TestCase):
    def setUp(self):
        import portal
        self.portal = portal
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), portal.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.port = self.server.server_address[1]

    def request(self, method, path, body=b'', content_type=None,
                headers=None):
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

    def get(self, path, headers=None):
        status, headers_out, body = self.request('GET', path, headers=headers)
        return status, headers_out, body.decode('utf-8', 'replace')

    def post_form(self, path, fields, headers=None):
        body = urllib.parse.urlencode(fields).encode()
        return self.request('POST', path, body=body,
                            content_type='application/x-www-form-urlencoded',
                            headers=headers)

    def db(self, sql, args=()):
        conn = sqlite3.connect(str(self.portal.DB))
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def outbox_rows(self, email, kind=None):
        sql = "SELECT subject,body,status FROM email_outbox WHERE recipient=?"
        args = [email]
        if kind:
            sql += " AND kind=?"
            args.append(kind)
        return self.db(sql, args)

    def suppress(self, email):
        """Opt an address out through the real helpers. Returns the token."""
        import email_unsubscribe
        with self.portal.db() as c:
            token = email_unsubscribe.get_or_create_token(c, email)
            self.assertTrue(
                email_unsubscribe.record_unsubscribe(c, email, token))
        return token

    def test_token_creation_and_url_format(self):
        import email_unsubscribe
        email = fresh_email()
        with self.portal.db() as c:
            token = email_unsubscribe.get_or_create_token(c, email)
            # token_urlsafe(24) -> 32 chars, URL-safe alphabet.
            self.assertEqual(len(token), 32)
            self.assertRegex(token, r'^[A-Za-z0-9_-]{32}$')
            # Stable: the same address always gets the same token.
            self.assertEqual(
                email_unsubscribe.get_or_create_token(c, email), token)
            # A token row is not an opt-out.
            self.assertFalse(email_unsubscribe.is_unsubscribed(c, email))
            url = email_unsubscribe.unsubscribe_url(
                email, 'http://127.0.0.1', token)
        self.assertIn('/unsubscribe?email=', url)
        self.assertIn('token=' + token, url)
        self.assertIn(urllib.parse.quote(email, safe=''), url)

    def test_append_footer(self):
        import email_unsubscribe
        body = email_unsubscribe.append_footer(
            'Hello.\n\n— VELXTRIA', 'a@example.com',
            'http://127.0.0.1', 'tok123')
        self.assertIn('To stop these emails: ', body)
        self.assertIn('/unsubscribe?email=a%40example.com&token=tok123',
                      body)

    def test_queue_skips_marketing_when_suppressed(self):
        import notifications
        email = fresh_email()
        self.suppress(email)
        with self.portal.db() as c:
            for kind in ('welcome', 'demo_followup', 'pro_upsell'):
                self.assertFalse(notifications.queue(
                    c, email, 'Subject', 'Body', kind,
                    dedupe_key='unsub-test:%s:%s' % (kind, email)))
        self.assertEqual(self.outbox_rows(email), [])

    def test_queue_still_queues_transactional_when_suppressed(self):
        import notifications
        email = fresh_email()
        self.suppress(email)
        with self.portal.db() as c:
            self.assertTrue(notifications.queue(
                c, email, 'Your VELXTRIA PRO is active', 'Body',
                'pro_activated', dedupe_key='unsub-test:pro:' + email))
            self.assertTrue(notifications.queue(
                c, email, 'Reset your VELXTRIA password', 'Body',
                'password_reset', dedupe_key='unsub-test:reset:' + email))
        rows = self.outbox_rows(email)
        self.assertEqual(len(rows), 2)

    def clear_outbox(self):
        # process_one() picks the oldest due row in the whole outbox,
        # and this module's DB is shared across tests, so drain it
        # before a process_one test or a leftover row gets picked first.
        conn = sqlite3.connect(str(self.portal.DB))
        try:
            conn.execute("DELETE FROM email_outbox")
            conn.commit()
        finally:
            conn.close()

    def test_process_one_skips_suppressed_marketing_row(self):
        import notifications
        email = fresh_email()
        self.clear_outbox()
        with self.portal.db() as c:
            self.assertTrue(notifications.queue(
                c, email, 'Subject', 'Body', 'welcome',
                dedupe_key='unsub-test:queued:' + email))
        # Opt out after queueing: the row must never send or retry.
        self.suppress(email)
        with patch.object(notifications, 'send_mail') as mock_send:
            with self.portal.db() as c:
                self.assertFalse(notifications.process_one(c))
            mock_send.assert_not_called()
            # Nothing left to process.
            with self.portal.db() as c:
                self.assertFalse(notifications.process_one(c))
        rows = self.outbox_rows(email, 'welcome')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], 'suppressed')

    def test_process_one_sends_marketing_when_not_suppressed(self):
        import notifications
        email = fresh_email()
        self.clear_outbox()
        with self.portal.db() as c:
            self.assertTrue(notifications.queue(
                c, email, 'Subject', 'Body', 'welcome',
                dedupe_key='unsub-test:send:' + email))
        with patch.object(notifications, 'send_mail') as mock_send:
            with self.portal.db() as c:
                self.assertTrue(notifications.process_one(c))
            mock_send.assert_called_once_with(email, 'Subject', 'Body')
        rows = self.outbox_rows(email, 'welcome')
        self.assertEqual(rows[0][2], 'sent')

    def test_unsubscribe_route_valid_token(self):
        import email_unsubscribe
        email = fresh_email()
        with self.portal.db() as c:
            token = email_unsubscribe.get_or_create_token(c, email)
            self.assertFalse(email_unsubscribe.is_unsubscribed(c, email))
        url = '/unsubscribe?email=%s&token=%s' % (
            urllib.parse.quote(email, safe=''), token)
        status, _, body = self.get(url)
        self.assertEqual(status, 200)
        self.assertIn('You are unsubscribed', body)
        self.assertIn('password resets', body)
        with self.portal.db() as c:
            self.assertTrue(email_unsubscribe.is_unsubscribed(c, email))

    def test_unsubscribe_route_invalid_token_404(self):
        import email_unsubscribe
        email = fresh_email()
        with self.portal.db() as c:
            token = email_unsubscribe.get_or_create_token(c, email)
        # Wrong token: 404, and the address stays subscribed.
        status, _, _ = self.get('/unsubscribe?email=%s&token=%s' % (
            urllib.parse.quote(email, safe=''), 'wrong-token'))
        self.assertEqual(status, 404)
        # Unknown email: same 404, no reveal.
        status, _, _ = self.get('/unsubscribe?email=%s&token=%s' % (
            urllib.parse.quote('nobody-here@example.com', safe=''), token))
        self.assertEqual(status, 404)
        # Missing params: same 404.
        status, _, _ = self.get('/unsubscribe')
        self.assertEqual(status, 404)
        with self.portal.db() as c:
            self.assertFalse(email_unsubscribe.is_unsubscribed(c, email))

    def test_marketing_bodies_contain_unsubscribe_link(self):
        import email_unsubscribe
        import followups
        email = fresh_email()
        # Welcome: queued by the register route itself.
        status, _, _ = self.post_form('/register', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        welcome = self.outbox_rows(email, 'welcome')
        self.assertEqual(len(welcome), 3)
        # Demo follow-up and PRO upsell: queued directly.
        with self.portal.db() as c:
            queued_demo = followups.queue_demo_sequence(
                c, email, 'tok123', 'http://127.0.0.1/demo/tok123',
                'http://127.0.0.1')
            user_id = self.db(
                'SELECT id FROM users WHERE email=?', (email,))[0][0]
            queued_pro = followups.queue_pro_upsell(
                c, user_id, email, 'http://127.0.0.1')
        self.assertEqual(queued_demo, 3)
        self.assertEqual(queued_pro, 2)
        with self.portal.db() as c:
            token = email_unsubscribe.get_or_create_token(c, email)
        for kind in ('welcome', 'demo_followup', 'pro_upsell'):
            rows = self.outbox_rows(email, kind)
            self.assertTrue(rows, 'no %s rows' % kind)
            for _subject, body, _status in rows:
                self.assertIn('/unsubscribe?email=', body)
                self.assertIn('token=' + token, body)

    def test_register_suppressed_user_gets_no_welcome(self):
        email = fresh_email()
        self.suppress(email)
        status, _, _ = self.post_form('/register', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        # The account is still created — only the marketing mail stops.
        self.assertTrue(self.db(
            'SELECT id FROM users WHERE email=?', (email,)))
        self.assertEqual(self.outbox_rows(email, 'welcome'), [])

    def test_record_unsubscribe_is_idempotent(self):
        import email_unsubscribe
        email = fresh_email()
        with self.portal.db() as c:
            token = email_unsubscribe.get_or_create_token(c, email)
            self.assertTrue(
                email_unsubscribe.record_unsubscribe(c, email, token))
            self.assertTrue(
                email_unsubscribe.record_unsubscribe(c, email, token))
            self.assertTrue(email_unsubscribe.is_unsubscribed(c, email))


if __name__ == '__main__':
    unittest.main()
