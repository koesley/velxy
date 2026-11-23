"""Tests for the Automatic Revenue Engine: follow-up sequences that turn
interest into PRO, on their own.

The funnel leaks at conversion, not at the demo: hundreds of people try
the demo, a few sign up, nobody pays. Two groups show real interest and
then hear nothing: demo leads (one report email, then silence) and
free-limit users (paywall, then no follow-up). This module queues
scheduled follow-up sequences for both groups. Each step is a row in
email_outbox with a future next_attempt, so the existing delivery worker
sends it when it comes due — nothing here sends mail directly, and
nothing needs a manual step. Every step has its own dedupe_key, so a
sequence is queued at most once per demo (or per user).

Sequences:
- Demo lead (per demo, keyed by email + share token): day 1, day 3,
  day 7.
- PRO upsell (per user, once ever): day 0 (the moment they hit the
  paywall) and day 3. Only for non-PRO users.

Both record a 'followup_queued' site event so /founder-stats shows the
engine working.

Run with:
  python -m unittest test_revenue_engine -v
"""
import http.client
import os
import re
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.parse
from http.server import ThreadingHTTPServer
from unittest.mock import patch

_TMP = None
_ENV = None

PASSWORD = 'RevPass123456!'

_EMAIL_N = [0]


def fresh_email():
    _EMAIL_N[0] += 1
    return 'rev-%d@example.com' % _EMAIL_N[0]


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
    _ENV.stop()
    _TMP.cleanup()
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class RevenueEngineTests(unittest.TestCase):
    def setUp(self):
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

    def outbox(self, kind, recipient):
        # Scoped by recipient: the DB is shared across tests in this
        # module, so an unscoped count would accumulate earlier tests'
        # rows. Each test uses a fresh email, so this isolates it.
        return self.db(
            "SELECT subject,next_attempt,body FROM email_outbox"
            " WHERE kind=? AND recipient=? ORDER BY next_attempt",
            (kind, recipient))

    def signed_in(self):
        email = fresh_email()
        status, _, _ = self.post_form('/register', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        status, headers, _ = self.post_form('/login', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        session = [p for p in headers['Set-Cookie'].split(',')
                   if 'velxtria_session=' in p][0].split(';')[0]
        headers = {'Cookie': session}
        _, _, text = self.get('/', headers=headers)
        csrf = re.search(r'name="csrf" value="([^"]+)"', text).group(1)
        return headers, csrf, email

    def burn_free_reports(self, headers, csrf):
        """Use the free report via the ledger, then hit the paywall."""
        for i in (1,):
            status, _, _ = self.post_form('/ledger/add', {
                'order_id': 'R-%d' % i, 'order_date': '2026-11-20',
                'customer': 'Ann', 'product': 'Window Cleaning',
                'quantity': '1', 'unit_price': '85.00', 'status': 'Paid',
                'region': 'Louisville', 'csrf': csrf}, headers=headers)
            self.assertEqual(status, 303)
            status, _, _ = self.post_form(
                '/ledger/report', {'csrf': csrf}, headers=headers)
            self.assertEqual(status, 303)
        status, _, _ = self.post_form(
            '/ledger/report', {'csrf': csrf}, headers=headers)
        self.assertEqual(status, 429, 'expected the paywall at the limit')

    def test_pro_upsell_queued_at_paywall(self):
        headers, csrf, email = self.signed_in()
        self.burn_free_reports(headers, csrf)
        rows = self.outbox('pro_upsell', email)
        self.assertEqual(len(rows), 2)
        subjects = [r[0] for r in rows]
        self.assertIn('You have used your free report — go PRO', subjects)
        self.assertIn('Still thinking about PRO?', subjects)
        # Day 0 is due now; day 3 is due ~72 hours out.
        now = int(time.time())
        dues = sorted(r[1] for r in rows)
        self.assertLessEqual(dues[0], now + 60)
        self.assertAlmostEqual(dues[1] - now, 3 * 86400, delta=120)
        # The upsell points at the account page, where checkout lives.
        body = rows[0][2]
        self.assertIn('/account', body)
        self.assertIn('$49', body)

    def test_pro_upsell_queued_once_ever(self):
        headers, csrf, email = self.signed_in()
        self.burn_free_reports(headers, csrf)
        self.assertEqual(len(self.outbox('pro_upsell', email)), 2)
        # Hitting the paywall again (and via the upload route) adds nothing.
        status, _, _ = self.post_form(
            '/ledger/report', {'csrf': csrf}, headers=headers)
        self.assertEqual(status, 429)
        self.assertEqual(len(self.outbox('pro_upsell', email)), 2)

    def test_demo_followup_sequence_queued(self):
        # Run the one-click sample demo, then leave an email for the report.
        status, _, body = self.request(
            'POST', '/try-sample', body=b'sample=1',
            content_type='application/x-www-form-urlencoded')
        self.assertEqual(status, 200)
        text = body.decode('utf-8', 'replace')
        token = re.search(r'/demo/(?!signup|email)([A-Za-z0-9_-]+)', text).group(1)
        email = fresh_email()
        status, _, _ = self.post_form(
            '/demo/email', {'email': email, 'share_token': token})
        self.assertEqual(status, 200)
        rows = self.outbox('demo_followup', email)
        self.assertEqual(len(rows), 3)
        subjects = [r[0] for r in rows]
        self.assertIn('Your VELXTRIA report is waiting', subjects)
        self.assertIn('Your demo results are still waiting', subjects)
        self.assertIn('Last chance to keep your VELXTRIA report', subjects)
        # Day 1, day 3, day 7 — none due immediately.
        now = int(time.time())
        dues = sorted(r[1] for r in rows)
        self.assertAlmostEqual(dues[0] - now, 86400, delta=120)
        self.assertAlmostEqual(dues[1] - now, 3 * 86400, delta=120)
        self.assertAlmostEqual(dues[2] - now, 7 * 86400, delta=120)
        # The first follow-up links the share page and the free signup.
        body = rows[0][2]
        self.assertIn('/demo/' + token, body)
        self.assertIn('/register', body)

    def test_demo_followup_not_requeued_on_resubmit(self):
        status, _, body = self.request(
            'POST', '/try-sample', body=b'sample=1',
            content_type='application/x-www-form-urlencoded')
        self.assertEqual(status, 200)
        text = body.decode('utf-8', 'replace')
        token = re.search(r'/demo/(?!signup|email)([A-Za-z0-9_-]+)', text).group(1)
        email = fresh_email()
        for _ in range(2):
            status, _, _ = self.post_form(
                '/demo/email', {'email': email, 'share_token': token})
            self.assertEqual(status, 200)
        self.assertEqual(len(self.outbox('demo_followup', email)), 3)

    def test_followup_events_recorded(self):
        before = self.db(
            "SELECT COUNT(*) FROM site_events WHERE event='followup_queued'")[0][0]
        # Scope the detail check to this test's events: the DB is shared
        # across modules, so the newest rows overall may belong to
        # another module's flow.
        max_rowid = self.db("SELECT MAX(rowid) FROM site_events")[0][0] or 0
        headers, csrf, email = self.signed_in()
        self.burn_free_reports(headers, csrf)
        after = self.db(
            "SELECT COUNT(*) FROM site_events WHERE event='followup_queued'")[0][0]
        # Two sequences fire in this flow: the welcome at signup and the
        # PRO upsell at the paywall.
        self.assertEqual(after - before, 2)
        details = [r[0] for r in self.db(
            "SELECT detail FROM site_events WHERE event='followup_queued'"
            " AND rowid > ?", (max_rowid,))]
        self.assertEqual(len(details), 2)
        self.assertTrue(any(d.startswith('welcome:') for d in details))
        self.assertTrue(any(d.startswith('pro:') for d in details))
