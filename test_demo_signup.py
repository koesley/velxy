"""Tests for the one-step demo signup (POST /demo/signup).

The funnel leaks at demo -> signup (197 demo runs, 1 signup): the old path
made an anonymous demo runner register, log in again with the same
password, then find the claim on the dashboard — five steps, two password
entries. Now the demo result page carries an inline email + password form
that creates the free account AND saves the demo report to it in a single
POST, landing the visitor on their saved report, already signed in.

Run with:
  python -m unittest test_demo_signup -v
"""
import http.client
import os
import re
import tempfile
import threading
import unittest
import urllib.parse
from http.server import ThreadingHTTPServer
from unittest.mock import patch

# The data dir must outlive the portal import: portal reads
# VELXTRIA_DATA_DIR once at module level, so a per-test temp dir would be
# deleted while later tests still use it.
_TMP = None
_ENV = None

PASSWORD = 'DemoPass123456!'

# Module-level counter: the data dir (and its users table) is shared by every
# test in this module, so emails must be unique across tests, not just
# within one test.
_EMAIL_N = [0]


def fresh_email():
    _EMAIL_N[0] += 1
    return 'demo-signup-%d@example.com' % _EMAIL_N[0]


def setUpModule():
    global _TMP, _ENV
    _TMP = tempfile.TemporaryDirectory()
    _ENV = patch.dict(os.environ, {
        'VELXTRIA_DATA_DIR': _TMP.name,
        'VELXTRIA_DEPLOYMENT_MODE': 'local',
        'VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT': '0',
    })
    _ENV.start()
    import portal  # noqa: F401  (imported for its module-level DATA_ROOT)
    # DATA_ROOT is fixed at first import, which may have happened in an
    # earlier test module whose temp dir is already deleted; recreate it so
    # sqlite can open the DB file again.
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


def tearDownModule():
    import portal
    _ENV.stop()
    _TMP.cleanup()
    # Leave DATA_ROOT in place: later modules reuse the same imported
    # portal, and a deleted data dir breaks their DB access.
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class DemoSignupTests(unittest.TestCase):
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

    def run_sample_demo(self):
        status, _, body = self.post_form('/try-sample', {'sample': '1'})
        self.assertEqual(status, 200)
        return body.decode('utf-8', 'replace')

    def demo_token(self, text):
        match = re.search(r'name="token" value="([A-Za-z0-9_-]+)"', text)
        self.assertIsNotNone(match, 'demo result has no signup token')
        return match.group(1)

    def signup_from_demo(self, email=None, password=PASSWORD, token=None):
        if token is None:
            token = self.demo_token(self.run_sample_demo())
        return self.post_form('/demo/signup', {
            'email': email or fresh_email(),
            'password': password, 'token': token})

    def test_demo_result_has_inline_signup_form(self):
        text = self.run_sample_demo()
        self.assertIn('action="/demo/signup"', text)
        self.assertIn('Save this report to my free account', text)
        self.assertIn('name="email"', text)
        self.assertIn('name="password"', text)
        self.assertIn('name="token"', text)

    def test_demo_signup_creates_account_claims_report_and_signs_in(self):
        email = fresh_email()
        with self.portal.db() as c:
            signup_before = c.execute(
                "SELECT count(*) FROM site_events WHERE event='signup'").fetchone()[0]
            generated_before = c.execute(
                "SELECT count(*) FROM site_events WHERE event='report_generated'").fetchone()[0]
        status, headers, _ = self.signup_from_demo(email=email)
        self.assertEqual(status, 303)
        location = headers.get('Location', '')
        self.assertTrue(location.startswith('/report?id='),
                        'signup did not land on the saved report: %r' % location)
        self.assertIn('velxtria_session=', headers.get('Set-Cookie', ''))
        with self.portal.db() as c:
            user = c.execute(
                'SELECT id FROM users WHERE email=?', (email,)).fetchone()
            self.assertIsNotNone(user, 'no user row created')
            report = c.execute(
                'SELECT id, accepted, rejected FROM reports WHERE user_id=?',
                (user[0],)).fetchone()
            self.assertIsNotNone(report, 'no report row created')
            self.assertEqual((report[1], report[2]), (6, 3))
            self.assertEqual(
                c.execute("SELECT count(*) FROM site_events WHERE event='signup'").fetchone()[0],
                signup_before + 1)
            self.assertEqual(
                c.execute("SELECT count(*) FROM site_events WHERE event='report_generated'").fetchone()[0],
                generated_before + 1)
        # Follow the redirect as the new user: the saved report renders.
        session = [p for p in headers['Set-Cookie'].split(',')
                   if 'velxtria_session=' in p][0].split(';')[0]
        status, _, body = self.get(location, headers={'Cookie': session})
        self.assertEqual(status, 200)
        self.assertIn('$800.00', body)
        self.assertIn('What we found wrong', body)

    def test_demo_signup_counts_against_free_allowance(self):
        email = fresh_email()
        status, _, _ = self.signup_from_demo(email=email)
        self.assertEqual(status, 303)
        with self.portal.db() as c:
            uid = c.execute(
                'SELECT id FROM users WHERE email=?', (email,)).fetchone()[0]
            import subscriptions
            _, count, remaining = subscriptions.usage(c, uid)
        self.assertEqual(count, 1)
        self.assertEqual(remaining, 2)

    def test_demo_signup_rejects_duplicate_email(self):
        email = fresh_email()
        status, _, _ = self.signup_from_demo(email=email)
        self.assertEqual(status, 303)
        status, _, body = self.signup_from_demo(email=email)
        self.assertEqual(status, 409)
        self.assertIn('already exists', body.decode('utf-8', 'replace'))

    def test_demo_signup_rejects_reused_token(self):
        token = self.demo_token(self.run_sample_demo())
        status, _, _ = self.signup_from_demo(token=token)
        self.assertEqual(status, 303)
        # The claim is one-time: the same token cannot save a second report.
        status, _, body = self.signup_from_demo(token=token)
        self.assertEqual(status, 400)
        self.assertIn('expired or was already claimed',
                      body.decode('utf-8', 'replace'))

    def test_demo_signup_rejects_bogus_token(self):
        status, _, body = self.signup_from_demo(token='bogus-token')
        self.assertEqual(status, 400)
        self.assertIn('expired or was already claimed',
                      body.decode('utf-8', 'replace'))

    def test_demo_signup_validates_email_and_password(self):
        status, _, _ = self.signup_from_demo(email='not-an-email')
        self.assertEqual(status, 400)
        status, _, _ = self.signup_from_demo(password='short')
        self.assertEqual(status, 400)

    def test_claim_demo_still_works_after_refactor(self):
        # The old signed-in claim path shares the new _save_demo_report
        # helper; a registered user must still be able to claim a demo.
        email = fresh_email()
        status, _, _ = self.post_form('/register', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        status, headers, _ = self.post_form('/login', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        session = [p for p in headers['Set-Cookie'].split(',')
                   if 'velxtria_session=' in p][0].split(';')[0]
        # Run a demo to get a claimable token, then claim it as the
        # signed-in user with the dashboard's CSRF token.
        token = self.demo_token(self.run_sample_demo())
        status, _, dash = self.get('/', headers={'Cookie': session})
        csrf = re.search(r'name="csrf" value="([A-Za-z0-9_-]+)"', dash)
        self.assertIsNotNone(csrf, 'no CSRF token on the dashboard')
        status, claim_headers, _ = self.post_form(
            '/claim-demo', {'token': token, 'csrf': csrf.group(1)},
            headers={'Cookie': session})
        self.assertEqual(status, 303)
        self.assertTrue(claim_headers.get('Location', '').startswith('/report?id='))
        # Count only this test's user: the reports table is shared across
        # test modules (portal.DATA_ROOT is fixed at first import), so a
        # bare count(*) would see other modules' reports.
        with self.portal.db() as c:
            user_id = c.execute(
                'SELECT id FROM users WHERE email=?', (email,)).fetchone()[0]
            self.assertEqual(
                c.execute('SELECT count(*) FROM reports WHERE user_id=?',
                          (user_id,)).fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
