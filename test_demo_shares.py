"""Tests for shareable demo results: a demo run gets a public /demo/<token>
link that shows only the aggregated summaries — never the file or a raw
row — and expires after 30 days. Run with:
  python -m unittest test_demo_shares -v
"""
import http.client
import os
import re
import sqlite3
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import demo_shares

_TMP = None
_ENV = None

TEST_CSV = (
    b'Order ID,Order Date,Customer,Product,Quantity,Unit Price,Status,Region\n'
    b'X-001,2026-10-03,Secret Customer,Window Cleaning,2,85.00,Paid,Louisville\n'
    b'X-002,2026-10-05,Secret Customer,Deep Cleaning,1,180.00,Paid,Louisville\n'
    b'X-003,not-a-date,Secret Customer,Gutter Cleaning,1,120.00,Paid,Louisville\n'
)

SAMPLE_REPORT = {
    'monthly_rows': [['Month', 'Revenue'], ['2026-10', '350.00']],
    'product_rows': [['Product', 'Revenue'], ['Window Cleaning', '170.00']],
    'stats': ['Paid revenue (accepted Paid orders only): $350.00'],
    'accepted': 2, 'rejected': 1,
}


class DemoShareUnitTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        demo_shares.setup(self.conn)

    def test_create_and_get_round_trip(self):
        token = demo_shares.create(self.conn, SAMPLE_REPORT)
        self.assertTrue(token)
        shared = demo_shares.get(self.conn, token)
        self.assertIsNotNone(shared)
        self.assertEqual(shared['monthly_rows'], SAMPLE_REPORT['monthly_rows'])
        self.assertEqual(shared['product_rows'], SAMPLE_REPORT['product_rows'])
        self.assertEqual(shared['stats'], SAMPLE_REPORT['stats'])
        self.assertEqual(shared['accepted'], 2)
        self.assertEqual(shared['rejected'], 1)

    def test_unknown_token_returns_none(self):
        self.assertIsNone(demo_shares.get(self.conn, 'no-such-token'))

    def test_expired_share_returns_none_and_is_dropped(self):
        token = demo_shares.create(self.conn, SAMPLE_REPORT)
        self.conn.execute('UPDATE demo_shares SET expires=? WHERE token=?',
                          (int(time.time()) - 1, token))
        self.assertIsNone(demo_shares.get(self.conn, token))
        self.assertIsNone(self.conn.execute(
            'SELECT 1 FROM demo_shares WHERE token=?', (token,)).fetchone())


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
    _ENV.stop()
    _TMP.cleanup()
    import portal
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class DemoShareFlowTests(unittest.TestCase):
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

    def get(self, path):
        status, headers, body = self.request('GET', path)
        return status, headers, body.decode('utf-8', 'replace')

    def post_multipart(self, path, filename, data):
        boundary = '----testboundary1234'
        head = ('--' + boundary + '\r\n'
                'Content-Disposition: form-data; name="file"; filename="%s"\r\n'
                'Content-Type: text/csv\r\n\r\n' % filename).encode()
        tail = ('\r\n--' + boundary + '--\r\n').encode()
        return self.request('POST', path, body=head + data + tail,
                            content_type='multipart/form-data; boundary=' + boundary)

    def run_demo(self):
        status, _, body = self.post_multipart('/try', 'sales.csv', TEST_CSV)
        self.assertEqual(status, 200)
        return body.decode('utf-8', 'replace')

    def test_demo_result_links_to_share_page(self):
        body = self.run_demo()
        match = re.search(r'/demo/(?!signup|email)([A-Za-z0-9_-]+)', body)
        self.assertTrue(match, 'demo result page has no share link')
        return match.group(1)

    def test_shared_page_shows_summaries_only(self):
        token = self.test_demo_result_links_to_share_page()
        status, _, body = self.get('/demo/' + token)
        self.assertEqual(status, 200)
        self.assertIn('$350.00', body)
        self.assertIn('Window Cleaning', body)
        self.assertIn('Try it with your own CSV', body)
        self.assertIn('/#try', body)
        # PRO takes card now too: no stale 'Bitcoin only' copy.
        self.assertIn('Bitcoin or card', body)
        self.assertNotIn('Bitcoin only', body)
        # Raw row values never appear: no order ids, no customer names.
        self.assertNotIn('X-001', body)
        self.assertNotIn('Secret Customer', body)

    def test_unknown_and_empty_share_tokens_404(self):
        status, _, _ = self.get('/demo/no-such-token')
        self.assertEqual(status, 404)
        status, _, _ = self.get('/demo/')
        self.assertEqual(status, 404)


if __name__ == '__main__':
    unittest.main()
