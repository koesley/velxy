"""Regression coverage for graceful instant-demo share failures."""
import http.client
import os
import re
import sqlite3
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from test_demo_shares import TEST_CSV


class DemoShareFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.env = patch.dict(os.environ, {
            'VELXTRIA_DATA_DIR': cls.tmp.name,
            'VELXTRIA_DEPLOYMENT_MODE': 'local',
            'VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT': '0',
        })
        cls.env.start()
        import portal
        cls.portal = portal
        portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
        portal.REPORTS.mkdir(parents=True, exist_ok=True)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), portal.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.env.stop()
        cls.tmp.cleanup()
        cls.portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
        cls.portal.REPORTS.mkdir(parents=True, exist_ok=True)

    def request(self, method, path, data=b'', content_type=None):
        conn = http.client.HTTPConnection('127.0.0.1',
                                          self.server.server_address[1], timeout=30)
        try:
            headers = {'Content-Type': content_type} if content_type else {}
            conn.request(method, path, body=data, headers=headers)
            response = conn.getresponse()
            return response.status, dict(response.headers), response.read()
        finally:
            conn.close()

    def run_demo(self):
        boundary = '----fallbacktestboundary'
        payload = (
            ('--' + boundary + '\r\n'
             'Content-Disposition: form-data; name="file"; filename="sales.csv"\r\n'
             'Content-Type: text/csv\r\n\r\n').encode()
            + TEST_CSV + ('\r\n--' + boundary + '--\r\n').encode()
        )
        return self.request('POST', '/try', payload,
                            'multipart/form-data; boundary=' + boundary)

    def assert_download_survives(self, error):
        with patch.object(self.portal.demo_shares, 'create', side_effect=error):
            status, headers, body = self.run_demo()
        self.assertEqual(status, 200)
        html = body.decode('utf-8', 'replace')
        self.assertIn('Public sharing is unavailable', html)
        self.assertNotIn('Share this result:', html)
        self.assertNotIn('/demo/', html)
        match = re.search(r'/try-download\?token=([A-Za-z0-9_-]+)', html)
        self.assertIsNotNone(match)
        status, _, archive = self.request('GET', '/try-download?token=' + match.group(1))
        self.assertEqual(status, 200)
        self.assertTrue(archive.startswith(b'PK'), 'Expected ZIP download')
        self.assertIn('velxtria_demo', headers.get('Set-Cookie', '').lower())

    def test_oversized_share_does_not_destroy_report(self):
        self.assert_download_survives(ValueError('summary exceeds storage limit'))

    def test_share_database_error_does_not_destroy_report(self):
        self.assert_download_survives(sqlite3.OperationalError('database is locked'))

    def test_share_overflow_does_not_destroy_report(self):
        self.assert_download_survives(OverflowError('integer too large'))

    def test_successful_share_still_visible(self):
        status, _, body = self.run_demo()
        self.assertEqual(status, 200)
        html = body.decode('utf-8', 'replace')
        self.assertIn('Share this result:', html)
        self.assertNotIn('Public sharing is unavailable', html)


if __name__ == '__main__':
    unittest.main()
