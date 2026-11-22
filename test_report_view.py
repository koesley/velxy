"""Tests for the saved-report view: a logged-in user sees a report's monthly
+ product summaries on screen instead of only inside the downloaded ZIP,
the dashboard links each report to its view, and an upload lands on the new
report's page. Static assets are cacheable while HTML pages stay no-store.
Run with:
  python -m unittest test_report_view -v
"""
import http.client
import io
import os
import re
import tempfile
import threading
import unittest
import urllib.parse
import zipfile
from http.server import ThreadingHTTPServer
from unittest.mock import patch

# The data dir must outlive the portal import: portal reads
# VELXTRIA_DATA_DIR once at module level, so a per-test temp dir would be
# deleted while later tests still use it.
_TMP = None
_ENV = None

# Module-level counter so every test gets a fresh user (a fresh 3-report
# quota); a per-test counter would re-register the same email and hit 409.
_USER_N = [0]
# messy (duplicate order, bad date, zero quantity), $800.00 paid revenue.
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
    with portal.db() as c:
        c.execute(
            'DELETE FROM referral_rewards WHERE referrer_id IN '
            "(SELECT id FROM users WHERE email LIKE 'rv%@example.test')")
        c.execute(
            'DELETE FROM referral_signups WHERE referrer_id IN '
            "(SELECT id FROM users WHERE email LIKE 'rv%@example.test')")
        c.execute(
            "DELETE FROM referrals WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE 'rv%@example.test')")
        c.execute(
            'DELETE FROM report_write_journal WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'rv%@example.test')")
        c.execute(
            'DELETE FROM reports WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'rv%@example.test')")
        c.execute(
            'DELETE FROM sessions WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'rv%@example.test')")
        c.execute("DELETE FROM users WHERE email LIKE 'rv%@example.test'")
    _ENV.stop()
    _TMP.cleanup()
    # Leave DATA_ROOT in place: later modules reuse the same imported
    # portal, and a deleted data dir breaks their DB access.
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class ReportViewTests(unittest.TestCase):
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
        headers = {'Cookie': 'velxtria_session=' + cookie} if cookie else None
        status, headers_out, body = self.request('GET', path, headers=headers)
        return status, headers_out, body.decode('utf-8', 'replace')

    def post_form(self, path, fields, cookie=None):
        body = urllib.parse.urlencode(fields).encode()
        headers = {'Cookie': 'velxtria_session=' + cookie} if cookie else None
        return self.request('POST', path, body=body,
                            content_type='application/x-www-form-urlencoded',
                            headers=headers)

    def user_id(self, email):
        with self.portal.db() as c:
            return c.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()[0]

    def csrf_for(self, email):
        with self.portal.db() as c:
            row = c.execute(
                'SELECT s.csrf FROM sessions s JOIN users u ON u.id=s.user_id '
                'WHERE u.email=? ORDER BY s.expires DESC LIMIT 1',
                (email,)).fetchone()
            return row[0]

    def sign_in(self, email):
        data = {'email': email, 'password': 'TestPass123456!'}
        status, headers, _ = self.post_form('/register', data)
        self.assertEqual(status, 303)
        status, headers, _ = self.post_form('/login', data)
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/')
        match = re.search(r'velxtria_session=([^;]+)', headers.get('Set-Cookie', ''))
        self.assertTrue(match, 'login did not set a session cookie')
        return match.group(1)

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

    def make_user_and_upload(self):
        """A fresh user (fresh 3-report quota) with one real report."""
        _USER_N[0] += 1
        email = 'rv%d@example.test' % _USER_N[0]
        cookie = self.sign_in(email)
        csrf = self.csrf_for(email)
        status, headers, _ = self.upload(cookie, csrf)
        self.assertEqual(status, 303)
        location = headers.get('Location', '')
        self.assertTrue(location.startswith('/report?id='),
                        'upload did not land on the report view: %s' % location)
        report_id = urllib.parse.parse_qs(
            urllib.parse.urlsplit(location).query)['id'][0]
        return email, cookie, report_id

    def test_upload_redirects_to_report_view(self):
        _, cookie, report_id = self.make_user_and_upload()
        status, _, body = self.get('/report?id=' + report_id, cookie)
        self.assertEqual(status, 200)
        self.assertIn('Monthly summary', body)
        self.assertIn('Product summary', body)
        self.assertIn('$800.00', body)
        self.assertIn('test-messy-sales.csv', body)
        self.assertIn('Accepted 6 rows', body)
        self.assertIn('flagged 3 rows', body)
        self.assertIn('/download?id=' + report_id, body)
        self.assertIn('Back to dashboard', body)

    def test_dashboard_lists_view_link(self):
        _, cookie, report_id = self.make_user_and_upload()
        status, _, body = self.get('/', cookie)
        self.assertEqual(status, 200)
        self.assertIn('/report?id=' + report_id, body)
        self.assertIn('>View<', body)

    def test_report_requires_login(self):
        _, _, report_id = self.make_user_and_upload()
        status, headers, _ = self.get('/report?id=' + report_id)
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/login')

    def test_report_unknown_id_404(self):
        email = 'rv404@example.test'
        cookie = self.sign_in(email)
        status, _, body = self.get('/report?id=' + '0' * 32, cookie)
        self.assertEqual(status, 404)
        self.assertIn('Report not found', body)

    def test_report_other_users_report_404(self):
        _, _, report_id = self.make_user_and_upload()
        other_cookie = self.sign_in('rvother@example.test')
        status, _, body = self.get('/report?id=' + report_id, other_cookie)
        self.assertEqual(status, 404)
        self.assertIn('Report not found', body)

    def test_report_missing_file_503(self):
        email = 'rvmissing@example.test'
        cookie = self.sign_in(email)
        ident = 'a' * 32
        with self.portal.db() as c:
            c.execute(
                'INSERT INTO reports(id,user_id,filename,created,status,'
                'accepted,rejected,digest) VALUES (?,?,?,?,?,?,?,?)',
                (ident, self.user_id(email), 'ghost.csv',
                 self.portal.now(), 'ready', 6, 3, 'x'))
        status, _, body = self.get('/report?id=' + ident, cookie)
        self.assertEqual(status, 503)
        self.assertIn('temporarily unavailable', body)

    def test_report_corrupt_zip_503(self):
        email = 'rvcorrupt@example.test'
        cookie = self.sign_in(email)
        ident = 'b' * 32
        uid = self.user_id(email)
        self.portal.persistent.store(uid, ident, b'not a zip', self.portal.REPORTS)
        with self.portal.db() as c:
            c.execute(
                'INSERT INTO reports(id,user_id,filename,created,status,'
                'accepted,rejected,digest) VALUES (?,?,?,?,?,?,?,?)',
                (ident, uid, 'broken.csv', self.portal.now(), 'ready', 6, 3, 'x'))
        status, _, body = self.get('/report?id=' + ident, cookie)
        self.assertEqual(status, 503)
        self.assertIn('Report integrity verification failed', body)

    def test_download_still_works(self):
        _, cookie, report_id = self.make_user_and_upload()
        status, _, data = self.request(
            'GET', '/download?id=' + report_id,
            headers={'Cookie': 'velxtria_session=' + cookie})
        self.assertEqual(status, 200)
        names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        self.assertEqual(names, self.portal.REPORT_FILES)

    def test_static_assets_cacheable_html_not(self):
        def cache_headers(resp):
            return [v for k, v in resp.getheaders()
                    if k.lower() == 'cache-control']

        # Static assets are cacheable for an hour. The stylesheet is
        # assembled from many modules at request time, so it additionally
        # revalidates once stale; the script is a plain file.
        expected = {'/style.css': 'public, max-age=3600, must-revalidate',
                    '/checkout-feedback.js': 'public, max-age=3600'}
        for path in ('/style.css', '/checkout-feedback.js'):
            conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
            try:
                conn.request('GET', path)
                resp = conn.getresponse()
                resp.read()
                cache = cache_headers(resp)
                self.assertEqual(len(cache), 1, '%s sent %d Cache-Control headers' % (path, len(cache)))
                self.assertEqual(cache[0], expected[path])
            finally:
                conn.close()
        _, cookie, _ = self.make_user_and_upload()
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
        try:
            conn.request('GET', '/', headers={'Cookie': 'velxtria_session=' + cookie})
            resp = conn.getresponse()
            resp.read()
            cache = cache_headers(resp)
            self.assertEqual(len(cache), 1)
            self.assertEqual(cache[0], 'no-store')
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()
