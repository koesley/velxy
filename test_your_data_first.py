"""Tests for the "your data first" demo.

The funnel leaks at demo -> signup (215 demo runs, 1 real signup): the
demo ran on SAMPLE data, so nobody cared about keeping the result — saving
a fictional report is not a reason to create an account. The fix makes the
visitor's OWN CSV the primary demo path:

* The landing demo section leads with the upload form ("what's wrong with
  YOUR data") and the one-click sample is the fallback ("No file handy?").
* The demo result page's signup/claim copy says YOUR report when the run
  used the visitor's own file, and "this report" for the sample.
* The funnel records own=1 for an uploaded CSV and sample=1 for the
  sample, so the split is visible in site_events.

Run with:
  python -m unittest test_your_data_first -v
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

PASSWORD = 'YourData123456!'

# Module-level counter: the data dir (and its users table) is shared by
# every test in this module, so emails must be unique across tests, not
# just within one test.
_EMAIL_N = [0]


def fresh_email():
    _EMAIL_N[0] += 1
    return 'your-data-first-%d@example.com' % _EMAIL_N[0]


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


class YourDataFirstTests(unittest.TestCase):
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

    def demo_section(self, text):
        start = text.find('<section id="try"')
        self.assertGreaterEqual(start, 0, 'landing page has no demo section')
        return text[start:start + 3000]

    def run_sample_demo(self, headers=None):
        status, _, body = self.post_form('/try-sample', {'sample': '1'},
                                         headers=headers)
        self.assertEqual(status, 200)
        return body.decode('utf-8', 'replace')

    def run_own_demo(self, headers=None):
        status, _, body = self.post_multipart('/try', 'sales.csv', TEST_CSV,
                                              headers=headers)
        self.assertEqual(status, 200)
        return body.decode('utf-8', 'replace')

    def latest_demo_run_detail(self):
        with self.portal.db() as c:
            row = c.execute(
                "SELECT detail FROM site_events WHERE event='demo_run' "
                "ORDER BY rowid DESC LIMIT 1").fetchone()
        self.assertIsNotNone(row, 'no demo_run event recorded')
        return row[0]

    def signed_in_headers(self):
        email = fresh_email()
        status, _, _ = self.post_form('/register', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        status, headers, _ = self.post_form('/login', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        session = [p for p in headers['Set-Cookie'].split(',')
                   if 'velxtria_session=' in p][0].split(';')[0]
        return {'Cookie': session}

    def test_landing_demo_section_upload_first(self):
        _, _, text = self.get('/')
        section = self.demo_section(text)
        upload = section.find('action="/try"')
        sample = section.find('action="/try-sample"')
        self.assertGreater(upload, 0, 'demo section has no upload form')
        self.assertGreater(sample, 0, 'demo section has no sample form')
        self.assertLess(upload, sample,
                        'upload form must come before the sample form')
        self.assertIn("what's wrong with YOUR data", section)
        self.assertIn('No file handy? Run the sample instead', section)
        self.assertIn('Run the sample — one click', section)

    def test_sample_demo_result_uses_sample_signup_copy(self):
        text = self.run_sample_demo()
        self.assertIn('Get the cleaned file', text)
        self.assertNotIn('Get YOUR cleaned file', text)
        self.assertIn('sample=1', self.latest_demo_run_detail())

    def test_own_csv_demo_result_uses_own_signup_copy(self):
        text = self.run_own_demo()
        self.assertIn('Get YOUR cleaned file', text)
        self.assertNotIn('Get the cleaned file', text)
        self.assertIn('own=1', self.latest_demo_run_detail())
        self.assertNotIn('sample=1', self.latest_demo_run_detail())

    def test_signed_in_own_demo_claim_uses_own_copy(self):
        headers = self.signed_in_headers()
        text = self.run_own_demo(headers=headers)
        self.assertIn('Save your report to my account', text)
        self.assertNotIn('Save this report to my account', text)

    def test_signed_in_sample_demo_claim_uses_sample_copy(self):
        headers = self.signed_in_headers()
        text = self.run_sample_demo(headers=headers)
        self.assertIn('Save this report to my account', text)
        self.assertNotIn('Save your report to my account', text)
