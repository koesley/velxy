"""Tests for the instant demo: no-signup CSV upload on the landing page.

A visitor can drop a sales CSV on the homepage and see the cleaned report
instantly — no account, no session, no stored file. The ZIP download lives
in memory for 10 minutes under a random token, and the demo never writes a
row to the database. Run with:
  python -m unittest test_instant_demo -v
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
    with portal.db() as c:
        c.execute(
            'DELETE FROM referral_rewards WHERE referrer_id IN '
            "(SELECT id FROM users WHERE email='demo@example.test')")
        c.execute(
            'DELETE FROM referral_signups WHERE referrer_id IN '
            "(SELECT id FROM users WHERE email='demo@example.test')")
        c.execute(
            "DELETE FROM referrals WHERE user_id IN "
            "(SELECT id FROM users WHERE email='demo@example.test')")
        c.execute(
            'DELETE FROM sessions WHERE user_id IN '
            "(SELECT id FROM users WHERE email='demo@example.test')")
        c.execute("DELETE FROM users WHERE email='demo@example.test'")
    _ENV.stop()
    _TMP.cleanup()
    # Leave DATA_ROOT in place: later modules reuse the same imported
    # portal, and a deleted data dir breaks their DB access.
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class InstantDemoTests(unittest.TestCase):
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
            return (resp.status, dict(resp.headers),
                    resp.read())
        finally:
            conn.close()

    def get(self, path, headers=None):
        status, headers_out, body = self.request('GET', path, headers=headers)
        return status, headers_out, body.decode('utf-8', 'replace')

    def post_multipart(self, path, filename, data):
        boundary = '----testboundary1234'
        head = ('--' + boundary + '\r\n'
                'Content-Disposition: form-data; name="file"; '
                'filename="' + filename + '"\r\n'
                'Content-Type: text/csv\r\n\r\n').encode()
        tail = ('\r\n--' + boundary + '--\r\n').encode()
        return self.request('POST', path, body=head + data + tail,
                            content_type='multipart/form-data; boundary=' + boundary)

    def count(self, table):
        with self.portal.db() as c:
            return c.execute('SELECT count(*) FROM ' + table).fetchone()[0]

    def test_landing_page_shows_demo_form(self):
        status, _, body = self.get('/')
        self.assertEqual(status, 200)
        self.assertIn('id="try"', body)
        self.assertIn('action="/try"', body)
        self.assertIn('Generate my report', body)
        self.assertIn('Order ID, Order Date, Customer, Product, Quantity, Unit Price, Status, Region', body)

    def test_public_sample_csv_download_matches_demo_schema(self):
        status, headers, data = self.request('GET', '/sample-sales.csv')
        self.assertEqual(status, 200)
        self.assertIn('text/csv', headers.get('Content-Type', ''))
        self.assertIn('attachment;', headers.get('Content-Disposition', ''))
        self.assertEqual(data.decode('utf-8'), self.portal.SAMPLE_SALES_CSV)
        self.assertTrue(data.startswith(b'Order ID,Order Date,Customer,Product,Quantity,Unit Price,Status,Region'))

    def test_sample_csv_can_run_through_anonymous_demo(self):
        status, _, data = self.request('GET', '/sample-sales.csv')
        self.assertEqual(status, 200)
        status, _, body = self.post_multipart('/try', 'VELXTRIA_Sample_Sales.csv', data)
        self.assertEqual(status, 200)
        self.assertIn(b'Accepted 6 rows', body)
        self.assertIn(b'flagged 3 rows', body)

    def test_landing_offers_sample_without_registration(self):
        status, _, body = self.get('/')
        self.assertEqual(status, 200)
        self.assertIn('href="/sample-sales.csv"', body)
        self.assertIn('Download the sample sales CSV', body)
        self.assertIn('fictional', body)

    def test_about_page_shows_demo_form(self):
        status, _, body = self.get('/about')
        self.assertEqual(status, 200)
        self.assertIn('action="/try"', body)

    def test_get_try_redirects_to_demo_section(self):
        status, headers, _ = self.get('/try')
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/#try')

    def test_demo_generates_report_on_screen(self):
        status, _, body = self.post_multipart('/try', 'sales.csv', TEST_CSV)
        self.assertEqual(status, 200)
        text = body.decode('utf-8')
        self.assertIn('Monthly summary', text)
        self.assertIn('Product summary', text)
        self.assertIn('$800.00', text)
        self.assertIn('Accepted 6 rows', text)
        self.assertIn('flagged 3 rows', text)
        self.assertIn('Window Cleaning', text)
        match = re.search(r'/try-download\?token=([A-Za-z0-9_-]+)', text)
        self.assertIsNotNone(match, 'result page has no download link')
        token = match.group(1)
        status, headers, zipped = self.request('GET', '/try-download?token=' + token)
        self.assertEqual(status, 200)
        self.assertIn('application/zip', headers.get('Content-Type', ''))
        with zipfile.ZipFile(io.BytesIO(zipped)) as z:
            self.assertEqual(sorted(z.namelist()), sorted([
                'cleaned_sales.csv', 'rejected_rows.csv', 'monthly_summary.csv',
                'product_summary.csv', 'run_summary.txt']))
            summary = z.read('run_summary.txt').decode('utf-8')
        self.assertIn('Paid revenue (accepted Paid orders only): $800.00', summary)

    def test_failed_claim_can_restore_demo_until_original_expiry(self):
        import portal
        token = portal.store_demo_zip(b'zip-data', 2, 1, 'sales.csv')
        entry = portal.claim_demo_zip(token)
        self.assertIsNotNone(entry)
        self.assertIsNone(portal.peek_demo_zip(token))
        self.assertTrue(portal.restore_demo_zip(token, entry))
        self.assertEqual(portal.take_demo_zip(token), b'zip-data')
        self.assertFalse(portal.restore_demo_zip(token, entry))
        self.assertEqual(portal.claim_demo_zip(token), entry)

    def test_expired_claim_is_not_restored(self):
        import portal
        token = portal.store_demo_zip(b'zip-data', 1, 0, 'sales.csv')
        entry = portal.claim_demo_zip(token)
        expired = (entry[0], 0, *entry[2:])
        self.assertFalse(portal.restore_demo_zip(token, expired))
        self.assertIsNone(portal.peek_demo_zip(token))

    def test_demo_download_unknown_token_404(self):
        status, _, body = self.get('/try-download?token=does-not-exist')
        self.assertEqual(status, 404)
        self.assertIn('expired', body)

    def test_demo_wrong_columns_rejected(self):
        status, _, body = self.post_multipart('/try', 'sales.csv', b'a,b,c\n1,2,3\n')
        self.assertEqual(status, 400)
        self.assertIn('Incorrect columns', body.decode('utf-8'))
        self.assertIn('Try another file', body.decode('utf-8'))

    def test_demo_no_file_rejected(self):
        body = urllib.parse.urlencode({'x': '1'}).encode()
        status, _, raw = self.request(
            'POST', '/try', body=body,
            content_type='application/x-www-form-urlencoded')
        self.assertEqual(status, 400)
        self.assertIn('Choose a CSV file', raw.decode('utf-8'))

    def test_demo_creates_nothing_in_database(self):
        self.get('/')  # warm up: creates the tables
        reports_before = self.count('reports')
        users_before = self.count('users')
        status, _, _ = self.post_multipart('/try', 'sales.csv', TEST_CSV)
        self.assertEqual(status, 200)
        self.assertEqual(self.count('reports'), reports_before)
        self.assertEqual(self.count('users'), users_before)

    def test_authenticated_upload_digest_matches_saved_zip(self):
        import hashlib
        import re
        import secrets
        import portal
        email = 'upload-integrity-' + secrets.token_hex(5) + '@example.test'
        form = urllib.parse.urlencode({
            'email': email, 'password': 'TestPass123456!',
        }).encode()
        uid = None
        report_id = None
        status, _, _ = self.request('POST', '/register', body=form,
                                    content_type='application/x-www-form-urlencoded')
        self.assertEqual(status, 303)
        status, headers, _ = self.request('POST', '/login', body=form,
                                          content_type='application/x-www-form-urlencoded')
        self.assertEqual(status, 303)
        cookie = headers['Set-Cookie'].split(';')[0]
        try:
            status, _, dashboard = self.request('GET', '/', headers={'Cookie': cookie})
            self.assertEqual(status, 200)
            match = re.search(rb'name="csrf" value="([^"]+)"', dashboard)
            self.assertIsNotNone(match)
            boundary = '----velxtriaUploadIntegrity'
            parts = [
                '--' + boundary,
                'Content-Disposition: form-data; name="csrf"',
                '',
                match.group(1).decode(),
                '--' + boundary,
                'Content-Disposition: form-data; name="file"; filename="sales.csv"',
                'Content-Type: text/csv',
                '',
                TEST_CSV.decode(),
                '--' + boundary + '--',
                '',
            ]
            payload = '\\r\\n'.join(parts).encode()
            status, headers, _ = self.request(
                'POST', '/upload', body=payload,
                content_type='multipart/form-data; boundary=' + boundary,
                headers={'Cookie': cookie})
            self.assertEqual(status, 303)
            location = headers['Location']
            self.assertTrue(location.startswith('/report?id='))
            report_id = location.split('id=', 1)[1]
            with portal.db() as c:
                uid, stored_digest = c.execute(
                    'SELECT user_id,digest FROM reports WHERE id=?', (report_id,)
                ).fetchone()
            status, _, zip_bytes = self.request(
                'GET', '/download?id=' + report_id, headers={'Cookie': cookie})
            self.assertEqual(status, 200)
            self.assertEqual(stored_digest, hashlib.sha256(zip_bytes).hexdigest())
            status, _, page = self.request('GET', location, headers={'Cookie': cookie})
            self.assertEqual(status, 200)
            self.assertIn(b'Window Cleaning', page)
        finally:
            if report_id:
                with portal.db() as c:
                    c.execute('DELETE FROM reports WHERE id=?', (report_id,))
                if uid is not None:
                    try:portal.persistent.remove(uid, report_id)
                    except Exception:pass
            with portal.db() as c:
                c.execute('DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE email=?)', (email,))
                c.execute('DELETE FROM users WHERE email=?', (email,))

    def test_saved_report_digest_rejects_tampered_download_and_view(self):
        import hashlib
        import secrets
        import portal
        email = 'integrity-' + secrets.token_hex(5) + '@example.test'
        password = 'TestPass123456!'
        form = urllib.parse.urlencode({'email': email, 'password': password}).encode()
        status, _, _ = self.request('POST', '/register', body=form,
                                    content_type='application/x-www-form-urlencoded')
        self.assertEqual(status, 303)
        status, headers, _ = self.request('POST', '/login', body=form,
                                          content_type='application/x-www-form-urlencoded')
        self.assertEqual(status, 303)
        cookie = headers['Set-Cookie'].split(';')[0]
        report_id = secrets.token_hex(16)
        original = portal.run_report_engine(TEST_CSV)['zip_bytes']
        digest = hashlib.sha256(original).hexdigest()
        try:
            with portal.db() as c:
                uid = c.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()[0]
                c.execute('INSERT INTO reports(id,user_id,filename,created,status,accepted,rejected,digest) VALUES (?,?,?,?,?,?,?,?)',
                          (report_id, uid, 'sales.csv', portal.now(), 'ready', 6, 3, digest))
            portal.persistent.store(uid, report_id, original, portal.REPORTS)
            headers = {'Cookie': cookie}
            status, _, _ = self.request('GET', '/download?id=' + report_id, headers=headers)
            self.assertEqual(status, 200)
            status, _, _ = self.request('GET', '/report?id=' + report_id, headers=headers)
            self.assertEqual(status, 200)
            # Same report identifier, valid ZIP bytes, but a different digest.
            tampered = portal.run_report_engine(TEST_CSV.replace(b'85.00', b'86.00'))['zip_bytes']
            portal.persistent.store(uid, report_id, tampered, portal.REPORTS)
            status, _, body = self.request('GET', '/download?id=' + report_id, headers=headers)
            self.assertEqual(status, 503)
            self.assertIn(b'integrity verification failed', body)
            status, _, body = self.request('GET', '/report?id=' + report_id, headers=headers)
            self.assertEqual(status, 503)
            self.assertIn(b'integrity verification failed', body)
        finally:
            with portal.db() as c:
                c.execute('DELETE FROM reports WHERE id=?', (report_id,))
                c.execute('DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE email=?)', (email,))
                c.execute('DELETE FROM users WHERE email=?', (email,))
            try:portal.persistent.remove(uid, report_id)
            except Exception:pass

    def test_logged_in_dashboard_has_no_demo_form(self):
        data = urllib.parse.urlencode({
            'email': 'demo@example.test',
            'password': 'TestPass123456!',
        }).encode()
        status, _, _ = self.request(
            'POST', '/register', body=data,
            content_type='application/x-www-form-urlencoded')
        self.assertEqual(status, 303)
        status, headers, _ = self.request(
            'POST', '/login', body=data,
            content_type='application/x-www-form-urlencoded')
        self.assertEqual(status, 303)
        cookie = headers.get('Set-Cookie', '').split(';')[0]
        self.assertIn('velxtria_session=', cookie)
        status, _, body = self.get('/', headers={'Cookie': cookie})
        self.assertEqual(status, 200)
        self.assertIn('Process a CSV', body)
        self.assertNotIn('action="/try"', body)
        self.assertNotIn('id="try"', body)


class ReportEngineTests(unittest.TestCase):
    def test_validate_rejects_oversized_nul_and_bad_encoding(self):
        import portal
        with self.assertRaisesRegex(ValueError, 'up to 5 MB'):
            portal.validate_csv_upload('sales.csv', b'x' * (portal.MAX_BYTES + 1))
        with self.assertRaisesRegex(ValueError, 'Invalid CSV file'):
            portal.validate_csv_upload('sales.csv', TEST_CSV + b'\x00')
        with self.assertRaisesRegex(ValueError, 'UTF-8'):
            portal.validate_csv_upload('sales.csv', b'\xff\xfe' + TEST_CSV)
        with self.assertRaisesRegex(ValueError, 'nonempty CSV'):
            portal.validate_csv_upload('sales.txt', TEST_CSV)

    def test_validate_rejects_over_line_limit(self):
        import portal
        header = TEST_CSV.splitlines()[0] + b'\n'
        row = TEST_CSV.splitlines()[1] + b'\n'
        big = header + row * 20001
        with self.assertRaisesRegex(ValueError, '20,000 lines'):
            portal.validate_csv_upload('sales.csv', big)

    def test_run_report_engine_returns_zip_and_summaries(self):
        import portal
        result = portal.run_report_engine(TEST_CSV)
        self.assertEqual(result['accepted'], 6)
        self.assertEqual(result['rejected'], 3)
        self.assertIn('Paid revenue (accepted Paid orders only): $800.00',
                      result['stats'])
        monthly = {r[0]: r for r in result['monthly_rows']}
        self.assertEqual(monthly['2026-10'], ['2026-10', '3', '470.00'])
        self.assertEqual(monthly['2026-11'], ['2026-11', '2', '330.00'])
        with zipfile.ZipFile(io.BytesIO(result['zip_bytes'])) as z:
            self.assertEqual(len(z.namelist()), 5)

    def test_demo_zip_store_expires_and_caps(self):
        import portal
        token = portal.store_demo_zip(b'zip-bytes', 6, 3, 'sales.csv')
        self.assertEqual(portal.take_demo_zip(token), b'zip-bytes')
        self.assertEqual(portal.peek_demo_zip(token)[2:], (6, 3, 'sales.csv'))
        # Expired entries are gone on the next read.
        portal._DEMO_ZIPS[token] = (b'stale', 0, 6, 3, 'sales.csv')
        self.assertIsNone(portal.take_demo_zip(token))
        self.assertNotIn(token, portal._DEMO_ZIPS)


if __name__ == '__main__':
    unittest.main()
