"""Tests for the welcome + activation sequence: the third leg of the
Automatic Revenue Engine.

The engine covered demo leads (day 1/3/7) and paywall hits (day 0/3),
but a new signup heard nothing after the account was created. The
funnel shows why that matters: 448 landing views, 280 demo runs, 4
signups, 1 checkout, 0 paid — and the 2 newest signups are test
accounts, so zero real signups have ever been activated. Demo-to-
Workspace made signup valuable (the demo's sales pre-seed the Sales
Ledger), but nothing told the new user about it or showed them the
next step, so the seeded ledger sat unused and the free report
never got touched.

Now every new signup gets a welcome sequence, queued once ever:
- Day 0: welcome. When the signup came from an own-CSV demo, the copy
  names the seeded ledger ("your sales are already in your Sales
  Ledger"); a plain register gets the generic welcome.
- Day 1: nudge the ledger (log a sale, or turn it into a report).
- Day 3: point at PRO ($49, 50 reports, Bitcoin).

Each step is an email_outbox row with a future next_attempt, sent by
the existing delivery worker; every step has its own dedupe_key, so a
sequence is queued at most once per user. The sequence is queued at
POST /register and at POST /demo/signup (seeded when the demo was the
visitor's own CSV, plain for a sample demo or a failed save), and it
can never break the signup.

Run with:
  python -m unittest test_welcome_sequence -v
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

PASSWORD = 'WelcomePass123456!'

_EMAIL_N = [0]


def fresh_email():
    _EMAIL_N[0] += 1
    return 'welcome-%d@example.com' % _EMAIL_N[0]


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


# The 9-row demo CSV (6 accepted, 3 flagged), as in test_demo_workspace.
TEST_CSV = b"""Order ID,Order Date,Customer,Product,Quantity,Unit Price,Status,Region
T-001,2026-10-02,Test Customer A,Window Cleaning,2,85.00,Paid,Louisville
T-002,2026-10-05,Test Customer B,Deep Cleaning,1,180.00,Paid,Louisville
T-003,2026-10-09,Test Customer A,Gutter Cleaning,1,120.00,Paid,Jeffersonville
T-004,2026-10-15,Test Customer C,Window Cleaning,3,85.00,Pending,Louisville
T-005,2026-11-02,Test Customer B,Deep Cleaning,1,180.00,Paid,Louisville
T-006,2026-11-09,Test Customer D,Pressure Washing,1,150.00,Paid,New Albany
T-007,2026-11-12,Test Customer E,Window Cleaning,1,85.00,Paid,Louisville
T-008,2026-11-15,Test Customer F,Deep Cleaning,0,180.00,Paid,Louisville
T-001,2026-10-02,Test Customer A,Window Cleaning,2,85.00,Paid,Louisville
"""


class WelcomeSequenceTests(unittest.TestCase):
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

    def post_multipart(self, path, filename, data, headers=None):
        boundary = '----testboundary1234'
        head = ('--' + boundary + '\r\n'
                'Content-Disposition: form-data; name="file"; '
                'filename="' + filename + '"\r\n'
                'Content-Type: text/csv\r\n\r\n').encode()
        tail = ('\r\n--' + boundary + '--\r\n').encode()
        return self.request('POST', path, body=head + data + tail,
                            content_type='multipart/form-data; boundary=' + boundary,
                            headers=headers)

    def db(self, sql, args=()):
        conn = sqlite3.connect(str(self.portal.DB))
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def outbox(self, email):
        # Scoped by recipient: the DB is shared across tests in this
        # module, so an unscoped count would accumulate earlier tests'
        # rows. Each test uses a fresh email, so this isolates it.
        return self.db(
            "SELECT subject,next_attempt,body FROM email_outbox"
            " WHERE kind='welcome' AND recipient=? ORDER BY next_attempt",
            (email,))

    def user_id(self, email):
        row = self.db('SELECT id FROM users WHERE email=?', (email,))
        return row[0][0] if row else None

    def demo_token(self, text):
        match = re.search(r'name="token" value="([A-Za-z0-9_-]+)"', text)
        self.assertIsNotNone(match, 'demo result has no token')
        return match.group(1)

    def run_own_demo(self):
        status, _, body = self.post_multipart('/try', 'sales.csv', TEST_CSV)
        self.assertEqual(status, 200)
        return body.decode('utf-8', 'replace')

    def run_sample_demo(self):
        status, _, body = self.post_form('/try-sample', {'sample': '1'})
        self.assertEqual(status, 200)
        return body.decode('utf-8', 'replace')

    def assert_welcome_shape(self, email, seeded):
        """The three steps (day 0, 1, 3) with the right subjects and due
        times; the day-0 copy names the seeded ledger only when seeded."""
        rows = self.outbox(email)
        self.assertEqual(len(rows), 3, 'expected 3 welcome steps, got %r' % (rows,))
        subjects = [r[0] for r in rows]
        self.assertIn('Your Sales Ledger is waiting', subjects)
        self.assertIn('You have free reports waiting', subjects)
        now = int(time.time())
        dues = sorted(r[1] for r in rows)
        self.assertLessEqual(dues[0], now + 60, 'day 0 is due now')
        self.assertAlmostEqual(dues[1] - now, 86400, delta=120)
        self.assertAlmostEqual(dues[2] - now, 3 * 86400, delta=120)
        day0 = [r for r in rows if r[1] <= now + 60][0]
        self.assertIn('1 free report', day0[2])
        if seeded:
            self.assertIn('Welcome to VELXTRIA — your workspace is ready',
                          [r[0] for r in rows])
            self.assertIn('already in your Sales Ledger', day0[2])
            self.assertIn('your dashboard opens on your real numbers', day0[2])
        else:
            self.assertIn('Welcome to VELXTRIA — your free account is ready',
                          [r[0] for r in rows])
            self.assertNotIn('already in your Sales Ledger', day0[2])
        # Day 1 points at the ledger, day 3 at PRO.
        day1 = [r for r in rows if 'Sales Ledger is waiting' in r[0]][0]
        self.assertIn('turn your ledger into a full cleaned report', day1[2])
        day3 = [r for r in rows if 'free reports waiting' in r[0]][0]
        self.assertIn('$49', day3[2])
        self.assertIn('/account', day3[2])

    def test_register_queues_welcome(self):
        email = fresh_email()
        status, _, _ = self.post_form('/register', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        self.assert_welcome_shape(email, seeded=False)

    def test_demo_signup_queues_seeded_welcome(self):
        text = self.run_own_demo()
        token = self.demo_token(text)
        email = fresh_email()
        status, headers, _ = self.post_form('/demo/signup', {
            'email': email, 'password': PASSWORD, 'token': token})
        self.assertEqual(status, 303)
        self.assertIn('/report?id=', headers.get('Location', ''))
        # The demo's sales were seeded, so the welcome names the ledger.
        self.assert_welcome_shape(email, seeded=True)

    def test_sample_demo_signup_queues_plain_welcome(self):
        text = self.run_sample_demo()
        token = self.demo_token(text)
        email = fresh_email()
        status, _, _ = self.post_form('/demo/signup', {
            'email': email, 'password': PASSWORD, 'token': token})
        self.assertEqual(status, 303)
        # The sample never seeds, so the welcome is the plain one.
        self.assert_welcome_shape(email, seeded=False)

    def test_welcome_queued_once_ever(self):
        email = fresh_email()
        status, _, _ = self.post_form('/register', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        self.assertEqual(len(self.outbox(email)), 3)
        # Queuing again for the same user adds nothing.
        import followups
        uid = self.user_id(email)
        self.assertIsNotNone(uid)
        with self.portal.db() as c:
            queued = followups.queue_welcome(
                c, uid, email, 'http://127.0.0.1', seeded=True)
        self.assertEqual(queued, 0)
        self.assertEqual(len(self.outbox(email)), 3)

    def test_welcome_event_recorded(self):
        before = self.db(
            "SELECT COUNT(*) FROM site_events WHERE event='followup_queued'")[0][0]
        email = fresh_email()
        status, _, _ = self.post_form('/register', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        after = self.db(
            "SELECT COUNT(*) FROM site_events WHERE event='followup_queued'")[0][0]
        self.assertEqual(after - before, 1)
        detail = self.db(
            "SELECT detail FROM site_events WHERE event='followup_queued'"
            " ORDER BY rowid DESC LIMIT 1")[0][0]
        self.assertTrue(detail.startswith('welcome:'))
