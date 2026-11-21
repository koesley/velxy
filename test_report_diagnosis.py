"""Tests for the on-screen "what we found wrong" diagnosis.

The engine's smartest output — each flagged row with its specific problem —
used to live only inside the downloaded ZIP, so a visitor saw the totals
but never the proof that the product understands their data. Now the demo
result, a saved report, and the landing sample show the flagged rows and a
cleaned sample on screen. The public share page deliberately does NOT show
raw rows (anyone with the link could read a stranger's customer names).

Run with:
  python -m unittest test_report_diagnosis -v
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
_USER_N = [0]

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
    with portal.db() as c:
        c.execute(
            'DELETE FROM referral_rewards WHERE referrer_id IN '
            "(SELECT id FROM users WHERE email LIKE 'dg%@example.test')")
        c.execute(
            'DELETE FROM referral_signups WHERE referrer_id IN '
            "(SELECT id FROM users WHERE email LIKE 'dg%@example.test')")
        c.execute(
            "DELETE FROM referrals WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE 'dg%@example.test')")
        c.execute(
            'DELETE FROM report_write_journal WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'dg%@example.test')")
        c.execute(
            'DELETE FROM reports WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'dg%@example.test')")
        c.execute(
            'DELETE FROM sessions WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'dg%@example.test')")
        c.execute("DELETE FROM users WHERE email LIKE 'dg%@example.test'")
    _ENV.stop()
    _TMP.cleanup()
    # Leave DATA_ROOT in place: later modules reuse the same imported
    # portal, and a deleted data dir breaks their DB access.
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class DiagnosisUnitTests(unittest.TestCase):
    def test_engine_returns_diagnosis_rows(self):
        import portal
        report = portal.run_report_engine(TEST_CSV)
        self.assertEqual(report['accepted'], 6)
        self.assertEqual(report['rejected'], 3)
        # Flagged rows: header + 3, each with the specific problem.
        flagged = report['rejected_rows']
        self.assertEqual(flagged[0][-1], 'Issue(s)')
        issues = [r[-1] for r in flagged[1:]]
        self.assertIn('duplicate order ID', issues)
        self.assertIn('invalid date', issues)
        self.assertIn('quantity must be a positive integer', issues)
        self.assertEqual(flagged[1][1], 'T-001')
        self.assertEqual(flagged[1][3], 'Test Customer E')
        # Cleaned sample: header + first 5 clean rows, Revenue computed.
        cleaned = report['cleaned_rows']
        self.assertEqual(cleaned[0][-1], 'Revenue')
        self.assertEqual(len(cleaned), 6)
        self.assertEqual(cleaned[1][0], 'T-001')
        self.assertEqual(cleaned[1][-1], '170.00')

    def test_diagnosis_html_shows_flagged_rows_and_issues(self):
        import portal
        report = portal.run_report_engine(TEST_CSV)
        html = portal.report_diagnosis_html(
            report['rejected_rows'], report['cleaned_rows'],
            report['rejected'], report['accepted'])
        self.assertIn('What we found wrong', html)
        self.assertIn('duplicate order ID', html)
        self.assertIn('invalid date', html)
        self.assertIn('quantity must be a positive integer', html)
        self.assertIn('Test Customer E', html)
        self.assertIn('T-007', html)
        # Issue summary counts each problem once.
        self.assertIn('duplicate order ID ×1', html)
        self.assertIn('invalid date ×1', html)

    def test_diagnosis_html_shows_cleaned_sample(self):
        import portal
        report = portal.run_report_engine(TEST_CSV)
        html = portal.report_diagnosis_html(
            report['rejected_rows'], report['cleaned_rows'],
            report['rejected'], report['accepted'])
        self.assertIn('Your data, cleaned', html)
        self.assertIn('Test Customer A', html)
        self.assertIn('170.00', html)
        self.assertIn('First 5 of 6 clean rows', html)

    def test_diagnosis_html_escapes_labels(self):
        import portal
        flagged = [['Source Line', 'Order ID', 'Order Date', 'Customer',
                    'Product', 'Quantity', 'Unit Price', 'Status', 'Region',
                    'Issue(s)'],
                   ['2', 'X-1', '2026-10-01', '<script>alert(1)</script>',
                    'Deep Cleaning', '1', '10.00', 'Paid', 'Louisville',
                    'invalid date']]
        cleaned = [['Order ID', 'Order Date', 'Customer', 'Product',
                    'Quantity', 'Unit Price', 'Status', 'Region', 'Revenue'],
                   ['X-2', '2026-10-02', '<b>Bold</b>', 'Window Cleaning',
                    '1', '85.00', 'Paid', 'Louisville', '85.00']]
        html = portal.report_diagnosis_html(flagged, cleaned, 1, 1)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertNotIn('<b>Bold</b>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('&lt;b&gt;Bold&lt;/b&gt;', html)

    def test_diagnosis_html_empty_when_no_data(self):
        import portal
        self.assertEqual(
            portal.report_diagnosis_html([], [], 0, 0), '')
        self.assertEqual(
            portal.report_diagnosis_html([['Source Line']], [], 0, 0), '')

    def test_diagnosis_html_caps_flagged_display(self):
        import portal
        head = ['Source Line', 'Order ID', 'Order Date', 'Customer',
                'Product', 'Quantity', 'Unit Price', 'Status', 'Region',
                'Issue(s)']
        rows = [head] + [
            [str(i + 2), 'X-%d' % i, '2026-10-01', 'Customer %d' % i,
             'Deep Cleaning', '1', '10.00', 'Paid', 'Louisville',
             'invalid date']
            for i in range(12)]
        html = portal.report_diagnosis_html(rows, [], 12, 0)
        self.assertIn('Showing 10 of 12 flagged rows', html)
        self.assertIn('Customer 9', html)
        self.assertNotIn('Customer 10', html)

    def test_read_report_summaries_returns_diagnosis_rows(self):
        import portal
        report = portal.run_report_engine(TEST_CSV)
        monthly, product, stats, flagged, cleaned = \
            portal.read_report_summaries(report['zip_bytes'])
        self.assertEqual(monthly, report['monthly_rows'])
        self.assertEqual(product, report['product_rows'])
        self.assertEqual([r[-1] for r in flagged[1:]], [
            'duplicate order ID', 'invalid date',
            'quantity must be a positive integer'])
        self.assertEqual(cleaned[1][0], 'T-001')
        self.assertEqual(cleaned[1][-1], '170.00')

    def test_read_report_summaries_without_diagnosis_files(self):
        import portal
        import io as _io
        import zipfile as _zf
        buf = _io.BytesIO()
        with _zf.ZipFile(buf, 'w') as z:
            z.writestr('monthly_summary.csv', 'Month,Paid Orders,Paid Revenue\n2026-10,1,100.00\n')
            z.writestr('product_summary.csv', 'Product,Paid Orders,Paid Revenue\nDeep Cleaning,1,100.00\n')
            z.writestr('run_summary.txt', 'Source rows: 1\nAccepted rows: 1\nRejected rows: 0\nPaid revenue (accepted Paid orders only): $100.00\n')
        monthly, product, stats, flagged, cleaned = \
            portal.read_report_summaries(buf.getvalue())
        self.assertEqual(monthly[1][0], '2026-10')
        self.assertEqual(flagged, [])
        self.assertEqual(cleaned, [])


class DiagnosisFlowTests(unittest.TestCase):
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

    def post_multipart(self, path, filename, data):
        boundary = '----testboundary1234'
        head = ('--' + boundary + '\r\n'
                'Content-Disposition: form-data; name="file"; '
                'filename="' + filename + '"\r\n'
                'Content-Type: text/csv\r\n\r\n').encode()
        tail = ('\r\n--' + boundary + '--\r\n').encode()
        return self.request('POST', path, body=head + data + tail,
                            content_type='multipart/form-data; boundary=' + boundary)

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
        match = re.search(r'velxtria_session=([^;]+)', headers.get('Set-Cookie', ''))
        self.assertTrue(match, 'login did not set a session cookie')
        return match.group(1)

    def upload(self, cookie, csrf):
        boundary = '----testboundary1234'
        parts = [
            ('--' + boundary + '\r\n'
             'Content-Disposition: form-data; name="csrf"\r\n\r\n'
             + csrf + '\r\n').encode(),
            ('--' + boundary + '\r\n'
             'Content-Disposition: form-data; name="file"; '
             'filename="test-messy-sales.csv"\r\n'
             'Content-Type: text/csv\r\n\r\n').encode(),
            TEST_CSV,
            ('\r\n--' + boundary + '--\r\n').encode(),
        ]
        return self.request('POST', '/upload', body=b''.join(parts),
                            content_type='multipart/form-data; boundary=' + boundary,
                            headers={'Cookie': 'velxtria_session=' + cookie})

    def test_demo_result_shows_diagnosis(self):
        status, _, body = self.post_multipart('/try', 'sales.csv', TEST_CSV)
        self.assertEqual(status, 200)
        text = body.decode('utf-8')
        self.assertIn('What we found wrong', text)
        self.assertIn('duplicate order ID', text)
        self.assertIn('invalid date', text)
        self.assertIn('quantity must be a positive integer', text)
        self.assertIn('Test Customer E', text)
        self.assertIn('Your data, cleaned', text)
        self.assertIn('170.00', text)
        # Charts and summaries still render above the diagnosis.
        self.assertIn('Revenue by month', text)
        self.assertIn('Monthly summary', text)

    def test_share_page_does_not_show_raw_rows(self):
        status, _, body = self.post_multipart('/try', 'sales.csv', TEST_CSV)
        self.assertEqual(status, 200)
        text = body.decode('utf-8')
        match = re.search(r'/demo/([A-Za-z0-9_-]+)', text)
        self.assertIsNotNone(match, 'result page has no share link')
        status, _, shared = self.get('/demo/' + match.group(1))
        self.assertEqual(status, 200)
        # Aggregates still show, but no raw customer names or issue text.
        self.assertIn('Revenue by month', shared)
        self.assertIn('$800.00', shared)
        self.assertNotIn('Test Customer E', shared)
        self.assertNotIn('duplicate order ID', shared)
        self.assertNotIn('What we found wrong', shared)

    def test_landing_sample_shows_diagnosis(self):
        status, _, body = self.get('/')
        self.assertEqual(status, 200)
        self.assertIn('What we found wrong', body)
        self.assertIn('duplicate order ID', body)
        self.assertIn('Your data, cleaned', body)

    def test_report_view_shows_diagnosis(self):
        _USER_N[0] += 1
        email = 'dg%d@example.test' % _USER_N[0]
        cookie = self.sign_in(email)
        csrf = self.csrf_for(email)
        status, headers, _ = self.upload(cookie, csrf)
        self.assertEqual(status, 303)
        location = headers.get('Location', '')
        self.assertTrue(location.startswith('/report?id='),
                        'upload did not land on the report view: %s' % location)
        status, _, body = self.get(location, cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn('What we found wrong', body)
        self.assertIn('duplicate order ID', body)
        self.assertIn('Test Customer E', body)
        self.assertIn('Your data, cleaned', body)


if __name__ == '__main__':
    unittest.main()
