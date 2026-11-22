"""Tests for Demo-to-Workspace: a demo builds your business.

The funnel leaks at demo -> signup (441 landing views, 276 demo runs, 2
signups): the demo knows the visitor's business — their products,
customers, revenue — and then throws it all away, so a new account opens
on an empty dashboard. Now, when an own-CSV demo is claimed into an
account (one-step signup or /claim-demo), the demo's accepted sales
become the starting Sales Ledger: the dashboard opens on the visitor's
real numbers instead of nothing. Sample demos never seed (the sample is
fictional), a row that cannot be stored is skipped, and seeding can never
fail the report save.

Run with:
  python -m unittest test_demo_workspace -v
"""
import csv
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

PASSWORD = 'WorkspacePass123456!'

# Module-level counter: the data dir (and its users table) is shared by every
# test in this module, so emails must be unique across tests, not just
# within one test.
_EMAIL_N = [0]


def fresh_email():
    _EMAIL_N[0] += 1
    return 'demo-workspace-%d@example.com' % _EMAIL_N[0]


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


# The 9-row demo CSV (6 accepted, 3 flagged), as in test_your_data_first.
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

CLEANED_HEADER = ['Order ID', 'Order Date', 'Customer', 'Product',
                  'Quantity', 'Unit Price', 'Status', 'Region', 'Revenue']


def make_zip(rows, filename='cleaned_sales.csv'):
    """A report ZIP holding a cleaned_sales.csv with the given rows (dicts
    keyed by the cleaned-sales columns)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=CLEANED_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        z.writestr(filename, out.getvalue())
    return buf.getvalue()


def good_row(order_id='W-001', **overrides):
    row = {'Order ID': order_id, 'Order Date': '2026-11-20',
           'Customer': 'Ann', 'Product': 'Window Cleaning', 'Quantity': '2',
           'Unit Price': '85.00', 'Status': 'Paid', 'Region': 'Louisville',
           'Revenue': '170.00'}
    row.update(overrides)
    return row


class DemoWorkspaceTests(unittest.TestCase):
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

    def register(self, email=None):
        email = email or fresh_email()
        status, _, _ = self.post_form('/register', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        with self.portal.db() as c:
            uid = c.execute('SELECT id FROM users WHERE email=?',
                            (email,)).fetchone()[0]
        return uid

    def signed_in(self, email=None):
        email = email or fresh_email()
        self.register(email)
        status, headers, _ = self.post_form('/login', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        session = [p for p in headers['Set-Cookie'].split(',')
                   if 'velxtria_session=' in p][0].split(';')[0]
        headers = {'Cookie': session}
        _, _, text = self.get('/', headers=headers)
        csrf = re.search(r'name="csrf" value="([^"]+)"', text).group(1)
        with self.portal.db() as c:
            uid = c.execute('SELECT id FROM users WHERE email=?',
                            (email,)).fetchone()[0]
        return headers, csrf, uid

    def demo_token(self, text):
        match = re.search(r'name="token" value="([A-Za-z0-9_-]+)"', text)
        self.assertIsNotNone(match, 'demo result has no token')
        return match.group(1)

    def run_own_demo(self, headers=None):
        status, _, body = self.post_multipart('/try', 'sales.csv', TEST_CSV,
                                              headers=headers)
        self.assertEqual(status, 200)
        return body.decode('utf-8', 'replace')

    def run_sample_demo(self, headers=None):
        status, _, body = self.post_form('/try-sample', {'sample': '1'},
                                         headers=headers)
        self.assertEqual(status, 200)
        return body.decode('utf-8', 'replace')

    def seeded_events(self):
        with self.portal.db() as c:
            row = c.execute(
                "SELECT COUNT(*) FROM site_events WHERE event='demo_workspace_seeded'").fetchone()
        return row[0] if row else 0

    # --- ledger.seed_from_zip_bytes, in isolation ---

    def test_seed_stores_cleaned_rows(self):
        import ledger
        uid = self.register()
        z = make_zip([good_row('W-001'), good_row('W-002', Product='Deep Cleaning', Quantity='1', **{'Unit Price': '180.00'}, Revenue='180.00')])
        with self.portal.db() as c:
            seeded = ledger.seed_from_zip_bytes(c, uid, z)
        self.assertEqual(seeded, 2)
        with self.portal.db() as c:
            self.assertEqual(ledger.count_entries(c, uid), 2)
            monthly, product, stats = ledger.summaries(c, uid)
        self.assertIn('Paid revenue: $350.00', stats)

    def test_seed_skips_duplicates_and_bad_rows(self):
        import ledger
        uid = self.register()
        rows = [good_row('W-001'),
                good_row('W-001'),  # duplicate order ID
                good_row('W-002', Quantity='0'),  # invalid quantity
                good_row('W-003', Product='Deep Cleaning', Quantity='1',
                         **{'Unit Price': '180.00'}, Revenue='180.00')]
        z = make_zip(rows)
        with self.portal.db() as c:
            seeded = ledger.seed_from_zip_bytes(c, uid, z)
        self.assertEqual(seeded, 2)
        with self.portal.db() as c:
            self.assertEqual(ledger.count_entries(c, uid), 2)

    def test_seed_second_run_seeds_nothing(self):
        import ledger
        uid = self.register()
        z = make_zip([good_row('W-001'), good_row('W-002')])
        with self.portal.db() as c:
            self.assertEqual(ledger.seed_from_zip_bytes(c, uid, z), 2)
            self.assertEqual(ledger.seed_from_zip_bytes(c, uid, z), 0)
            self.assertEqual(ledger.count_entries(c, uid), 2)

    def test_seed_ignores_zip_without_cleaned_file(self):
        import ledger
        uid = self.register()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('monthly_summary.csv', 'Month,Paid Orders\n')
        with self.portal.db() as c:
            self.assertEqual(ledger.seed_from_zip_bytes(c, uid, buf.getvalue()), 0)
            self.assertEqual(ledger.seed_from_zip_bytes(c, uid, b'not a zip'), 0)
            self.assertEqual(ledger.seed_from_zip_bytes(c, uid, b''), 0)

    def test_seed_respects_limit(self):
        import ledger
        uid = self.register()
        rows = [good_row('W-%03d' % n) for n in range(1, 8)]
        z = make_zip(rows)
        with self.portal.db() as c:
            self.assertEqual(ledger.seed_from_zip_bytes(c, uid, z, limit=3), 3)
            self.assertEqual(ledger.count_entries(c, uid), 3)

    # --- end to end: demo -> signup/claim -> ledger ---

    def test_own_demo_signup_seeds_ledger(self):
        text = self.run_own_demo()
        token = self.demo_token(text)
        before = self.seeded_events()
        status, headers, _ = self.post_form('/demo/signup', {
            'email': fresh_email(), 'password': PASSWORD, 'token': token})
        self.assertEqual(status, 303)
        self.assertIn('/report?id=', headers.get('Location', ''))
        session = [p for p in headers['Set-Cookie'].split(',')
                   if 'velxtria_session=' in p][0].split(';')[0]
        _, _, dash = self.get('/', headers={'Cookie': session})
        # The demo's 6 accepted sales are now the ledger: 6 logged, $800
        # paid (Oct $470 + Nov $330), with the demo's own order IDs.
        self.assertIn('6 sales logged', dash)
        self.assertIn('800.00', dash)
        self.assertIn('470.00', dash)
        self.assertIn('330.00', dash)
        # The recent-entries table shows the 5 newest; T-006 is the newest.
        self.assertIn('T-006', dash)
        self.assertIn('Window Cleaning', dash)
        self.assertEqual(self.seeded_events(), before + 1)

    def test_sample_demo_signup_does_not_seed(self):
        text = self.run_sample_demo()
        token = self.demo_token(text)
        before = self.seeded_events()
        status, headers, _ = self.post_form('/demo/signup', {
            'email': fresh_email(), 'password': PASSWORD, 'token': token})
        self.assertEqual(status, 303)
        session = [p for p in headers['Set-Cookie'].split(',')
                   if 'velxtria_session=' in p][0].split(';')[0]
        _, _, dash = self.get('/', headers={'Cookie': session})
        # The sample is fictional: the ledger stays empty.
        self.assertIn('no CSV', dash)
        self.assertNotIn('sales logged', dash)
        self.assertEqual(self.seeded_events(), before)

    def test_own_demo_claim_seeds_ledger(self):
        headers, csrf, uid = self.signed_in()
        text = self.run_own_demo(headers=headers)
        token = self.demo_token(text)
        before = self.seeded_events()
        status, headers_out, _ = self.post_form(
            '/claim-demo', {'token': token, 'csrf': csrf}, headers=headers)
        self.assertEqual(status, 303)
        self.assertIn('/report?id=', headers_out.get('Location', ''))
        _, _, dash = self.get('/', headers=headers)
        self.assertIn('6 sales logged', dash)
        self.assertIn('800.00', dash)
        self.assertIn('T-006', dash)
        self.assertEqual(self.seeded_events(), before + 1)
        import ledger
        with self.portal.db() as c:
            self.assertEqual(ledger.count_entries(c, uid), 6)

    def test_signup_page_promises_workspace(self):
        text = self.run_own_demo()
        self.assertIn('Sales Ledger', text)
        self.assertIn('your dashboard opens on your real numbers', text)


if __name__ == '__main__':
    unittest.main()
