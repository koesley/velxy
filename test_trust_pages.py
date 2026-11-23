"""Tests for the trust pages: terms, privacy, contact, favicon, and the
sitemap. Run with: python -m unittest test_trust_pages -v
"""
import http.client
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

_TMP = None
_ENV = None


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


class TrustPagesTests(unittest.TestCase):
    def setUp(self):
        import portal
        self.portal = portal
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), portal.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.port = self.server.server_address[1]

    def get(self, path):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
        try:
            conn.request('GET', path)
            resp = conn.getresponse()
            return (resp.status, dict(resp.headers),
                    resp.read().decode('utf-8', 'replace'))
        finally:
            conn.close()

    def test_terms(self):
        status, _, body = self.get('/terms')
        self.assertEqual(status, 200)
        self.assertIn('Terms of Service', body)
        self.assertIn('card through Stripe', body)
        self.assertIn('$49', body)

    def test_privacy(self):
        status, _, body = self.get('/privacy')
        self.assertEqual(status, 200)
        self.assertIn('Privacy Policy', body)
        self.assertIn('sells nothing', body)
        self.assertIn('No third-party trackers', body)

    def test_contact(self):
        status, _, body = self.get('/contact')
        self.assertEqual(status, 200)
        self.assertIn('Contact', body)
        self.assertIn('vincenthalay2005@gmail.com', body)

    def test_favicon(self):
        for path in ('/favicon.svg', '/favicon.ico'):
            status, headers, body = self.get(path)
            self.assertEqual(status, 200)
            self.assertIn('svg', headers.get('Content-Type', ''))
            self.assertIn('<svg', body)
        status, _, body = self.get('/')
        self.assertIn('rel="icon" href="/favicon.svg"', body)

    def test_landing_links_to_trust_pages(self):
        status, _, body = self.get('/')
        self.assertEqual(status, 200)
        self.assertIn('href="/terms"', body)
        self.assertIn('href="/privacy"', body)
        self.assertIn('href="/contact"', body)

    def test_sitemap_lists_trust_pages(self):
        status, _, body = self.get('/sitemap.xml')
        self.assertEqual(status, 200)
        for path in ('/terms', '/privacy', '/contact'):
            self.assertIn(path, body)

    def test_robots_does_not_block_trust_pages(self):
        status, _, body = self.get('/robots.txt')
        self.assertEqual(status, 200)
        for path in ('/terms', '/privacy', '/contact'):
            self.assertNotIn('Disallow: ' + path, body)


if __name__ == '__main__':
    unittest.main()
