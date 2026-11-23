"""Tests for the one-click sample demo (POST /try-sample).

A visitor should be able to experience the full demo — the real engine on
the built-in sample data, with charts, diagnosis, ZIP download and share
link — with a single click: no download, no upload, no account, no file to
find. The upload demo (/try) keeps working exactly as before.

Run with:
  python -m unittest test_sample_demo -v
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

# Same messy 9-row file the end-to-end browser test uses: 6 clean rows, 3
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
    _ENV.stop()
    _TMP.cleanup()
    # Leave DATA_ROOT in place: later modules reuse the same imported
    # portal, and a deleted data dir breaks their DB access.
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


_EMAIL_N = [0]


def _next_email():
    _EMAIL_N[0] += 1
    return 'sample-demo-%d@example.com' % _EMAIL_N[0]


class SampleDemoTests(unittest.TestCase):
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

    def post_multipart(self, path, filename, data):
        boundary = '----testboundary1234'
        head = ('--' + boundary + '\r\n'
                'Content-Disposition: form-data; name="file"; '
                'filename="' + filename + '"\r\n'
                'Content-Type: text/csv\r\n\r\n').encode()
        tail = ('\r\n--' + boundary + '--\r\n').encode()
        return self.request('POST', path, body=head + data + tail,
                            content_type='multipart/form-data; boundary=' + boundary)

    def run_sample_demo(self, headers=None):
        status, _, body = self.post_form('/try-sample', {'sample': '1'}, headers)
        self.assertEqual(status, 200)
        return body.decode('utf-8', 'replace')

    def _signed_in_cookie(self):
        email = _next_email()
        status, _, _ = self.post_form('/register', {
            'email': email, 'password': 'SamplePass123456!'})
        self.assertEqual(status, 303, 'register failed')
        status, headers, _ = self.post_form('/login', {
            'email': email, 'password': 'SamplePass123456!'})
        self.assertEqual(status, 303, 'login failed')
        return [p for p in headers.get('Set-Cookie', '').split(',')
                if 'velxtria_session=' in p][0].split(';')[0]

    def test_landing_page_has_one_click_sample_button(self):
        status, _, body = self.get('/')
        self.assertEqual(status, 200)
        # The button appears twice: in the hero actions and in the demo
        # section above the upload form.
        self.assertEqual(body.count('action="/try-sample"'), 2)
        self.assertIn('RUN THE SAMPLE', body)
        self.assertIn('Run the sample', body)
        # The form carries a hidden field so the POST has a body (an empty
        # form POST is rejected as "no form data received").
        self.assertIn('name="sample" value="1"', body)

    def test_sample_demo_returns_preview(self):
        # Anonymous runners get a preview, not the full result: the full
        # flagged list, the full cleaned file and the ZIP unlock with a
        # free account (the freemium demo). The preview still proves the
        # engine works — summaries, charts, issue counts and a taste of
        # the diagnosis.
        text = self.run_sample_demo()
        self.assertIn('Monthly summary', text)
        self.assertIn('Product summary', text)
        self.assertIn('$800.00', text)
        self.assertIn('Accepted 6 rows', text)
        self.assertIn('flagged 3 rows', text)
        # Charts and a diagnosis preview render on the sample result too.
        self.assertIn('Revenue by month', text)
        self.assertIn('Revenue by product', text)
        self.assertIn('What we found wrong', text)
        self.assertIn('duplicate order ID', text)
        self.assertIn('Your data, cleaned', text)
        self.assertIn('Showing 2 of 3 flagged rows', text)
        self.assertIn('unlock with a free account', text)
        # No ZIP download for an anonymous runner.
        self.assertNotIn('Download report ZIP', text)
        # The one-step signup is the unlock.
        self.assertIn('Save this report to my free account', text)
        match = re.search(r'/demo/(?!signup|email)([A-Za-z0-9_-]+)', text)
        self.assertIsNotNone(match, 'result page has no share link')

    def test_sample_demo_zip_downloads_signed_in(self):
        # The ZIP download is behind the free account now, so a signed-in
        # runner is the one who gets the link.
        cookie = self._signed_in_cookie()
        text = self.run_sample_demo(headers={'Cookie': cookie})
        match = re.search(r'/try-download\?token=([A-Za-z0-9_-]+)', text)
        self.assertIsNotNone(match, 'result page has no download link')
        status, headers, zipped = self.request(
            'GET', '/try-download?token=' + match.group(1))
        self.assertEqual(status, 200)
        self.assertIn('application/zip', headers.get('Content-Type', ''))
        with zipfile.ZipFile(io.BytesIO(zipped)) as z:
            self.assertEqual(sorted(z.namelist()), sorted([
                'cleaned_sales.csv', 'rejected_rows.csv', 'monthly_summary.csv',
                'product_summary.csv', 'run_summary.txt']))
            summary = z.read('run_summary.txt').decode('utf-8')
        self.assertIn('Paid revenue (accepted Paid orders only): $800.00', summary)

    def test_sample_demo_records_demo_run(self):
        self.run_sample_demo()
        with self.portal.db() as c:
            row = c.execute(
                "SELECT detail FROM site_events WHERE event='demo_run' "
                'ORDER BY rowid DESC LIMIT 1').fetchone()
        self.assertIsNotNone(row, 'no demo_run event recorded')
        self.assertIn('sample=1', row[0])
        self.assertIn('accepted=6', row[0])
        self.assertIn('rejected=3', row[0])

    def test_sample_demo_share_page_has_no_raw_rows(self):
        text = self.run_sample_demo()
        match = re.search(r'/demo/(?!signup|email)([A-Za-z0-9_-]+)', text)
        self.assertIsNotNone(match, 'result page has no share link')
        status, _, shared = self.get('/demo/' + match.group(1))
        self.assertEqual(status, 200)
        self.assertIn('Revenue by month', shared)
        self.assertIn('$800.00', shared)
        self.assertNotIn('Sample Customer', shared)
        self.assertNotIn('duplicate order ID', shared)
        self.assertNotIn('What we found wrong', shared)

    def test_get_try_sample_redirects_to_demo_section(self):
        status, headers, _ = self.get('/try-sample')
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/#try')

    def test_upload_demo_still_works_after_refactor(self):
        # The /try handler now shares its tail with /try-sample; an upload
        # must still produce the full result page.
        status, _, body = self.post_multipart('/try', 'sales.csv', TEST_CSV)
        self.assertEqual(status, 200)
        text = body.decode('utf-8', 'replace')
        self.assertIn('$800.00', text)
        self.assertIn('What we found wrong', text)
        self.assertIn('Revenue by month', text)


if __name__ == '__main__':
    unittest.main()
