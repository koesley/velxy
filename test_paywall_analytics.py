"""Tests for the paywall upsell and the built-in analytics.

Paywall: a user who has used all 3 free reports and uploads again sees
a PRO checkout page instead of a bare error — the real BTCPay form when
checkout is on, the manual-arrangement text when it is off.
Analytics: landing/demo/signup/report/checkout events land in the
site_events table and the founder-only /founder-stats page shows the
funnel; customers and anonymous visitors are kept out.
Run with:
  python -m unittest test_paywall_analytics -v
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

_TMP = None
_ENV = None

_USER_N = [0]
TEST_CSV = b"""Order ID,Order Date,Customer,Product,Quantity,Unit Price,Status,Region
T-001,2026-10-02,Test Customer A,Window Cleaning,2,85.00,Paid,Louisville
T-002,2026-10-05,Test Customer B,Deep Cleaning,1,180.00,Paid,Louisville
T-003,2026-10-09,Test Customer A,Gutter Cleaning,1,120.00,Paid,Jeffersonville
T-004,2026-10-15,Test Customer C,Window Cleaning,3,85.00,Pending,Louisville
T-005,2026-11-01,Test Customer B,Deep Cleaning,1,180.00,Paid,Louisville
T-006,2026-11-08,Test Customer D,Pressure Washing,1,150.00,Paid,New Albany
T-001,2026-11-10,Test Customer E,Window Cleaning,1,85.00,Paid,Louisville
T-007,not-a-date,Test Customer F,Deep Cleaning,1,180.00,Paid,Louisville
T-008,2026-11-12,Test Customer G,Gutter Cleaning,0,120.00,Paid,Louisville
"""


def setUpModule():
    global _TMP, _ENV
    _TMP = tempfile.TemporaryDirectory()
    _ENV = patch.dict(os.environ, {
        'VELXTRIA_DATA_DIR': _TMP.name,
        'VELXTRIA_DEPLOYMENT_MODE': 'local',
        # Dummy BTCPay config so checkout_enabled() is True and the
        # paywall renders the real form (no invoice is ever created here).
        'VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT': '1',
        'VELXTRIA_BTCPAY_MAINNET_URL': 'https://btcpay.example.com',
        'VELXTRIA_BTCPAY_MAINNET_STORE_ID': 'store123',
        'VELXTRIA_BTCPAY_MAINNET_API_KEY': 'key123',
    })
    _ENV.start()
    import portal  # noqa: F401
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


def tearDownModule():
    import portal
    with portal.db() as c:
        c.execute(
            'DELETE FROM reports WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'pa%@example.test')")
        c.execute(
            'DELETE FROM sessions WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'pa%@example.test')")
        c.execute("DELETE FROM users WHERE email LIKE 'pa%@example.test'")
        c.execute('DELETE FROM site_events')
    _ENV.stop()
    _TMP.cleanup()
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class PaywallAnalyticsTests(unittest.TestCase):
    def setUp(self):
        import portal
        self.portal = portal
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), portal.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.port = self.server.server_address[1]
        with portal.db() as c:
            c.execute('DELETE FROM site_events')

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
        headers = {'Cookie': 'velxtria_session=' + cookie} if cookie else None
        status, headers_out, body = self.request('GET', path, headers=headers)
        return status, headers_out, body.decode('utf-8', 'replace')

    def post_form(self, path, fields, cookie=None):
        body = urllib.parse.urlencode(fields).encode()
        headers = {'Cookie': 'velxtria_session=' + cookie} if cookie else None
        return self.request('POST', path, body=body,
                            content_type='application/x-www-form-urlencoded',
                            headers=headers)

    def csrf_for(self, email):
        with self.portal.db() as c:
            row = c.execute(
                'SELECT s.csrf FROM sessions s JOIN users u ON u.id=s.user_id '
                'WHERE u.email=? ORDER BY s.expires DESC LIMIT 1',
                (email,)).fetchone()
            return row[0]

    def event_count(self, event):
        with self.portal.db() as c:
            return c.execute(
                'SELECT count(*) FROM site_events WHERE event=?',
                (event,)).fetchone()[0]

    def sign_in(self, email):
        data = {'email': email, 'password': 'TestPass123456!'}
        status, headers, _ = self.post_form('/register', data)
        self.assertEqual(status, 303)
        status, headers, _ = self.post_form('/login', data)
        self.assertEqual(status, 303)
        match = re.search(r'velxtria_session=([^;]+)', headers.get('Set-Cookie', ''))
        self.assertTrue(match, 'login did not set a session cookie')
        return match.group(1)

    def make_admin(self):
        _USER_N[0] += 1
        email = 'pa%d@example.test' % _USER_N[0]
        cookie = self.sign_in(email)
        with self.portal.db() as c:
            c.execute("UPDATE users SET role='admin' WHERE email=?", (email,))
        return email, cookie

    def upload(self, cookie, csrf, filename='test-messy-sales.csv'):
        boundary = '----testboundary1234'
        parts = [
            ('--' + boundary + '\r\n'
             'Content-Disposition: form-data; name="csrf"\r\n\r\n'
             + csrf + '\r\n').encode(),
            ('--' + boundary + '\r\n'
             'Content-Disposition: form-data; name="file"; '
             'filename="' + filename + '"\r\n'
             'Content-Type: text/csv\r\n\r\n').encode(),
            TEST_CSV,
            ('\r\n--' + boundary + '--\r\n').encode(),
        ]
        return self.request('POST', '/upload', body=b''.join(parts),
                            content_type='multipart/form-data; boundary=' + boundary,
                            headers={'Cookie': 'velxtria_session=' + cookie})

    def demo(self):
        boundary = '----testboundary1234'
        parts = [
            ('--' + boundary + '\r\n'
             'Content-Disposition: form-data; name="file"; '
             'filename="test-messy-sales.csv"\r\n'
             'Content-Type: text/csv\r\n\r\n').encode(),
            TEST_CSV,
            ('\r\n--' + boundary + '--\r\n').encode(),
        ]
        status, _, body = self.request(
            'POST', '/try', body=b''.join(parts),
            content_type='multipart/form-data; boundary=' + boundary)
        return status, body.decode('utf-8', 'replace')

    def test_paywall_shows_checkout_after_3_free_reports(self):
        _USER_N[0] += 1
        email = 'pa%d@example.test' % _USER_N[0]
        cookie = self.sign_in(email)
        csrf = self.csrf_for(email)
        for _ in range(3):
            status, _, _ = self.upload(cookie, csrf)
            self.assertEqual(status, 303)
        status, _, body = self.upload(cookie, csrf)
        body = body.decode('utf-8', 'replace')
        self.assertEqual(status, 429)
        self.assertIn('You have used your 3 free reports', body)
        self.assertIn('Pay $49 with Bitcoin', body)
        self.assertIn('action="/btcpay/mainnet/checkout"', body)
        self.assertIn('Back to dashboard', body)
        self.assertEqual(self.event_count('paywall_shown'), 1)
        with self.portal.db() as c:
            used = c.execute(
                'SELECT count(*) FROM reports WHERE user_id='
                '(SELECT id FROM users WHERE email=?)', (email,)).fetchone()[0]
        self.assertEqual(used, 3, 'paywalled upload must not create a report')

    def test_paywall_manual_text_when_checkout_disabled(self):
        _USER_N[0] += 1
        email = 'pa%d@example.test' % _USER_N[0]
        cookie = self.sign_in(email)
        csrf = self.csrf_for(email)
        for _ in range(3):
            status, _, _ = self.upload(cookie, csrf)
            self.assertEqual(status, 303)
        with patch.dict(os.environ, {'VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT': '0'}):
            status, _, body = self.upload(cookie, csrf)
        body = body.decode('utf-8', 'replace')
        self.assertEqual(status, 429)
        self.assertIn('You have used your 3 free reports', body)
        self.assertIn('manual arrangement only', body)
        self.assertNotIn('action="/btcpay/mainnet/checkout"', body)

    def test_funnel_events_recorded_and_stats_page_shows_them(self):
        status, _, body = self.get('/')
        self.assertEqual(status, 200)
        self.assertIn('TRY IT NOW', body)
        status, _, _ = self.get('/about')
        self.assertEqual(status, 200)
        status, body = self.demo()
        self.assertEqual(status, 200)
        self.assertIn('$800.00', body)
        _USER_N[0] += 1
        email = 'pa%d@example.test' % _USER_N[0]
        cookie = self.sign_in(email)
        csrf = self.csrf_for(email)
        status, _, _ = self.upload(cookie, csrf)
        self.assertEqual(status, 303)
        self.assertEqual(self.event_count('landing_view'), 1)
        self.assertEqual(self.event_count('about_view'), 1)
        self.assertEqual(self.event_count('demo_run'), 1)
        self.assertEqual(self.event_count('signup'), 1)
        self.assertEqual(self.event_count('report_generated'), 1)
        _, admin_cookie = self.make_admin()
        status, _, body = self.get('/founder-stats', admin_cookie)
        self.assertEqual(status, 200)
        self.assertIn('Funnel', body)
        self.assertIn('Landing page views', body)
        self.assertIn('Demo reports generated', body)
        self.assertIn('Accounts created', body)
        self.assertIn('Last 14 days', body)
        self.assertIn('Recent events', body)

    def test_founder_stats_requires_admin(self):
        status, _, body = self.get('/founder-stats')
        self.assertEqual(status, 401)
        self.assertIn('Please sign in first', body)
        _USER_N[0] += 1
        email = 'pa%d@example.test' % _USER_N[0]
        cookie = self.sign_in(email)
        status, _, body = self.get('/founder-stats', cookie)
        self.assertEqual(status, 403)
        self.assertIn('Founder access required', body)

    def test_site_stats_summary_buckets_days(self):
        import site_stats
        import time
        now = int(time.time())
        with self.portal.db() as c:
            site_stats.record(c, 'landing_view', created=now - 86400)
            site_stats.record(c, 'landing_view', created=now - 86400)
            site_stats.record(c, 'demo_run', created=now)
            totals, daily, recent = site_stats.summary(c, days=14)
        self.assertEqual(totals['landing_view'], 2)
        self.assertEqual(totals['demo_run'], 1)
        self.assertEqual(len(daily), 2)
        self.assertEqual(daily[0][1].get('landing_view'), 2)
        self.assertEqual(daily[1][1].get('demo_run'), 1)
        self.assertEqual(len(recent), 3)


if __name__ == '__main__':
    unittest.main()
