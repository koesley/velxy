"""Tests for demo-to-account claiming: an instant demo report can be saved
into the account as a report (one free report), from the result page while
signed in, or from the dashboard after signing up. Run with:
  python -m unittest test_demo_claim -v
"""
import hashlib
import http.client
import os
import re
import tempfile
import threading
import time
import unittest
import urllib.parse
from http.server import ThreadingHTTPServer
from unittest.mock import patch

_TMP = None
_ENV = None
_USER_N = [0]

TEST_CSV = (
    b'Order ID,Order Date,Customer,Product,Quantity,Unit Price,Status,Region\n'
    b'X-001,2026-10-03,Secret Customer,Window Cleaning,2,85.00,Paid,Louisville\n'
    b'X-002,2026-10-05,Secret Customer,Deep Cleaning,1,180.00,Paid,Louisville\n'
    b'X-003,not-a-date,Secret Customer,Gutter Cleaning,1,120.00,Paid,Louisville\n'
)


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
    with portal.db() as c:
        c.execute(
            'DELETE FROM referral_rewards WHERE referrer_id IN '
            "(SELECT id FROM users WHERE email LIKE 'dc%@example.test')")
        c.execute(
            'DELETE FROM referral_signups WHERE referrer_id IN '
            "(SELECT id FROM users WHERE email LIKE 'dc%@example.test')")
        c.execute(
            "DELETE FROM referrals WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE 'dc%@example.test')")
        c.execute(
            'DELETE FROM reports WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'dc%@example.test')")
        c.execute(
            'DELETE FROM sessions WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'dc%@example.test')")
        c.execute(
            "DELETE FROM btcpay_orders WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE 'dc%@example.test')")
        c.execute(
            'DELETE FROM subscriptions WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'dc%@example.test')")
        c.execute("DELETE FROM users WHERE email LIKE 'dc%@example.test'")
    _ENV.stop()
    _TMP.cleanup()
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class DemoClaimTests(unittest.TestCase):
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

    def post_multipart(self, path, filename, data, cookie=None):
        boundary = '----testboundary1234'
        head = ('--' + boundary + '\r\n'
                'Content-Disposition: form-data; name="file"; filename="%s"\r\n'
                'Content-Type: text/csv\r\n\r\n' % filename).encode()
        tail = ('\r\n--' + boundary + '--\r\n').encode()
        headers = {'Cookie': cookie} if cookie else None
        return self.request('POST', path, body=head + data + tail,
                            content_type='multipart/form-data; boundary=' + boundary,
                            headers=headers)

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
        email = 'dc%d@example.test' % _USER_N[0]
        return email, self.sign_in(email)

    def user_id(self, email):
        with self.portal.db() as c:
            return c.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()[0]

    def csrf_for(self, email):
        with self.portal.db() as c:
            return c.execute(
                'SELECT csrf FROM sessions WHERE user_id=?',
                (self.user_id(email),)).fetchone()[0]

    def run_demo(self, cookie=None):
        status, headers, body = self.post_multipart(
            '/try', 'sales.csv', TEST_CSV, cookie)
        self.assertEqual(status, 200)
        # The demo token travels in the velxtria_demo cookie for everyone;
        # signed-in users also get it in the claim form.
        match = re.search(r'velxtria_demo=([^;]+)', headers.get('Set-Cookie', ''))
        self.assertTrue(match, 'demo result set no velxtria_demo cookie')
        return match.group(1), headers.get('Set-Cookie', '')

    def use_free_reports(self, email, count=3):
        uid = self.user_id(email)
        with self.portal.db() as c:
            for i in range(count):
                c.execute(
                    'INSERT INTO reports'
                    '(id,user_id,filename,created,status,accepted,rejected,digest)'
                    ' VALUES (?,?,?,?,?,?,?,?)',
                    ('used%d-%d' % (uid, i), uid, 'old.csv', int(time.time()),
                     'ready', 2, 1, hashlib.sha256(b'x').hexdigest()))

    def test_claim_from_result_page_saves_report(self):
        email, cookie = self.new_user()
        token, _ = self.run_demo(cookie)
        status, headers, _ = self.post_form(
            '/claim-demo', {'csrf': self.csrf_for(email), 'token': token}, cookie)
        self.assertEqual(status, 303)
        self.assertTrue(headers.get('Location', '').startswith('/report?id='))
        report_id = headers['Location'].split('id=')[1]
        status, _, body = self.get('/report?id=' + report_id, cookie)
        self.assertEqual(status, 200)
        self.assertIn('$350.00', body)
        with self.portal.db() as c:
            row = c.execute(
                'SELECT accepted,rejected,status FROM reports WHERE id=?',
                (report_id,)).fetchone()
        self.assertEqual(row, (2, 1, 'ready'))

    def test_claim_consumes_demo_once(self):
        email, cookie = self.new_user()
        token, _ = self.run_demo(cookie)
        status, _, _ = self.post_form(
            '/claim-demo', {'csrf': self.csrf_for(email), 'token': token}, cookie)
        self.assertEqual(status, 303)
        status, _, body = self.post_form(
            '/claim-demo', {'csrf': self.csrf_for(email), 'token': token}, cookie)
        self.assertEqual(status, 400)
        self.assertIn('already claimed', body)

    def test_claim_requires_login(self):
        status, headers, _ = self.post_form('/claim-demo', {'token': 'whatever'})
        self.assertEqual(status, 401)

    def test_claim_bogus_token(self):
        email, cookie = self.new_user()
        status, _, body = self.post_form(
            '/claim-demo', {'csrf': self.csrf_for(email), 'token': 'nope'}, cookie)
        self.assertEqual(status, 400)

    def test_claim_at_free_limit_shows_paywall_and_keeps_demo(self):
        email, cookie = self.new_user()
        self.use_free_reports(email, 3)
        token, _ = self.run_demo(cookie)
        status, _, body = self.post_form(
            '/claim-demo', {'csrf': self.csrf_for(email), 'token': token}, cookie)
        self.assertEqual(status, 429)
        self.assertIn('You have used your 3 free reports', body)
        status, _, _ = self.get('/try-download?token=' + token)
        self.assertEqual(status, 200)

    def test_anonymous_demo_claimable_from_dashboard(self):
        token, set_cookie = self.run_demo()
        self.assertIn('velxtria_demo=' + token, set_cookie)
        email, cookie = self.new_user()
        status, _, body = self.get('/', cookie + '; velxtria_demo=' + token)
        self.assertEqual(status, 200)
        self.assertIn('Your demo report is waiting', body)
        status, headers, _ = self.post_form(
            '/claim-demo', {'csrf': self.csrf_for(email), 'token': token}, cookie)
        self.assertEqual(status, 303)
        self.assertTrue(headers.get('Location', '').startswith('/report?id='))
        self.assertIn('velxtria_demo=', headers.get('Set-Cookie', ''))
        self.assertIn('Max-Age=0', headers.get('Set-Cookie', ''))


if __name__ == '__main__':
    unittest.main()
