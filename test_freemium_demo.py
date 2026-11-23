"""Tests for the freemium demo: the demo proves it, the account unlocks it.

The funnel leaks at demo -> signup (232 demo runs, 2 signups): the demo
gave the FULL report away for free — the flagged-row diagnosis, the
cleaned file and the ZIP download, all with no account — so there was no
reason to create one. The demo was cannibalising the signup. The fix is a
freemium demo:

* Anonymous runners get a PREVIEW: monthly + product summaries, charts,
  the issue counts, and a taste of the diagnosis (first 2 flagged rows,
  first 2 clean rows), plus a clear unlock note. The full flagged list,
  the full cleaned file and the ZIP download are behind the free account
  — the one-step signup form is the unlock.
* Signed-in runners get the FULL result exactly as before: all flagged
  rows, the full cleaned sample and the ZIP download.
* The public landing-page sample report (fictional data, a marketing
  asset) still shows the full diagnosis — it is not a demo run.

Run with:
  python -m unittest test_freemium_demo -v
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

# Same messy 9-row file the other demo tests use: 6 clean rows, 3 messy
# (duplicate order, bad date, zero quantity), $800.00 paid revenue.
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

PASSWORD = 'Freemium123456!'

# Module-level counter: the data dir (and its users table) is shared by
# every test in this module, so emails must be unique across tests, not
# just within one test.
_EMAIL_N = [0]


def fresh_email():
    _EMAIL_N[0] += 1
    return 'freemium-%d@example.com' % _EMAIL_N[0]


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


class FreemiumDemoTests(unittest.TestCase):
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

    def assert_preview(self, text, first, second, third):
        """The anonymous preview: summaries, charts, issue counts and a
        taste of the diagnosis — but not the full list or the ZIP. `first`,
        `second`, `third` are the flagged order IDs in order."""
        self.assertIn('Monthly summary', text)
        self.assertIn('Product summary', text)
        self.assertIn('$800.00', text)
        self.assertIn('Revenue by month', text)
        self.assertIn('Revenue by product', text)
        self.assertIn('What we found wrong', text)
        # Issue counts are computed from ALL flagged rows, so the summary
        # is accurate even though only 2 rows are shown.
        self.assertIn('duplicate order ID', text)
        self.assertIn('invalid date', text)
        self.assertIn('quantity must be a positive integer', text)
        self.assertIn('Showing 2 of 3 flagged rows', text)
        self.assertIn('unlock with a free account', text)
        # Only the first 2 flagged rows are shown; the 3rd is gated.
        self.assertIn(first, text)
        self.assertIn(second, text)
        self.assertNotIn(third, text)
        # Only the first 2 clean rows are shown.
        self.assertIn('First 2 of 6 clean rows', text)
        self.assertNotIn('Download report ZIP', text)

    def assert_full(self, text, first, second, third):
        """The signed-in full result: every flagged row, the full cleaned
        sample and the ZIP download."""
        self.assertIn('Monthly summary', text)
        self.assertIn('Product summary', text)
        self.assertIn('$800.00', text)
        self.assertIn('What we found wrong', text)
        self.assertIn(first, text)
        self.assertIn(second, text)
        self.assertIn(third, text)
        self.assertIn('First 5 of 6 clean rows', text)
        self.assertNotIn('Showing 2 of 3 flagged rows', text)
        self.assertNotIn('unlock with a free account', text)
        self.assertIn('Download report ZIP', text)

    def test_anonymous_sample_demo_is_preview(self):
        text = self.run_sample_demo()
        self.assert_preview(text, 'S-1001', 'S-1007', 'S-1008')
        self.assertIn('Save this report to my free account', text)
        match = re.search(r'/demo/(?!signup|email)([A-Za-z0-9_-]+)', text)
        self.assertIsNotNone(match, 'result page has no share link')

    def test_anonymous_own_demo_is_preview(self):
        text = self.run_own_demo()
        self.assert_preview(text, 'T-001', 'T-007', 'T-008')
        self.assertIn('Save your report to my free account', text)
        self.assertNotIn('Save this report to my free account', text)

    def test_anonymous_signup_form_comes_before_diagnosis(self):
        # The funnel leaks at demo -> signup (290 demo runs, 6 signups):
        # the signup form sat at the very bottom of the result, below the
        # summaries, the diagnosis preview and the share link, so a runner
        # who saw their numbers never had to scroll to it. The form now
        # sits right after the summaries, before the diagnosis preview,
        # so the "keep this report" offer is visible as soon as the
        # result lands. Both the sample and the own-file demo.
        for text in (self.run_sample_demo(), self.run_own_demo()):
            form = text.find('action="/demo/signup"')
            self.assertNotEqual(form, -1, 'anonymous result has no signup form')
            preview = text.find('Showing 2 of')
            self.assertNotEqual(preview, -1, 'anonymous result has no preview marker')
            self.assertLess(form, preview, 'signup form must come before the diagnosis preview')
            # The old note promised a download the anonymous page never
            # linked ("Your download expires in 10 minutes"); the note
            # now says plainly that the preview is temporary.
            self.assertNotIn('Your download expires in 10 minutes', text)
            self.assertIn('This preview is temporary', text)

    def test_signed_in_sample_demo_is_full(self):
        headers = self.signed_in_headers()
        text = self.run_sample_demo(headers=headers)
        self.assert_full(text, 'S-1001', 'S-1007', 'S-1008')
        self.assertIn('Save this report to my account', text)

    def test_signed_in_own_demo_is_full(self):
        headers = self.signed_in_headers()
        text = self.run_own_demo(headers=headers)
        self.assert_full(text, 'T-001', 'T-007', 'T-008')
        self.assertIn('Save your report to my account', text)

    def test_signed_in_demo_zip_downloads(self):
        headers = self.signed_in_headers()
        text = self.run_sample_demo(headers=headers)
        match = re.search(r'/try-download\?token=([A-Za-z0-9_-]+)', text)
        self.assertIsNotNone(match, 'result page has no download link')
        status, hdrs, zipped = self.request(
            'GET', '/try-download?token=' + match.group(1))
        self.assertEqual(status, 200)
        self.assertIn('application/zip', hdrs.get('Content-Type', ''))
        with zipfile.ZipFile(io.BytesIO(zipped)) as z:
            self.assertEqual(sorted(z.namelist()), sorted([
                'cleaned_sales.csv', 'rejected_rows.csv', 'monthly_summary.csv',
                'product_summary.csv', 'run_summary.txt']))
            summary = z.read('run_summary.txt').decode('utf-8')
        self.assertIn('Paid revenue (accepted Paid orders only): $800.00', summary)

    def test_landing_sample_report_stays_full(self):
        # The landing page's public sample report is fictional marketing
        # data, not a demo run — it still shows the full diagnosis.
        _, _, text = self.get('/')
        self.assertIn('What we found wrong', text)
        self.assertIn('S-1001', text)
        self.assertIn('S-1007', text)
        self.assertIn('S-1008', text)
