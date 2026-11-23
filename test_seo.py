"""Tests for the public SEO surface: meta description + Open Graph tags
on the landing page, and public robots.txt / sitemap.xml that let Google
index the landing and about pages while keeping everything behind a
login out of the index.
Run with:
  python -m unittest test_seo -v
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

DESCRIPTION = ('VELXTRIA turns messy sales CSVs into clean monthly and '
               'product reports for small service businesses. Free demo, '
               'no signup. PRO $49/30 days, Bitcoin or card.')


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
    import portal
    _ENV.stop()
    _TMP.cleanup()
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class SeoTests(unittest.TestCase):
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
            return resp.status, dict(resp.headers), resp.read().decode('utf-8', 'replace')
        finally:
            conn.close()

    def test_landing_has_meta_description_and_og_tags(self):
        self.assertEqual(len(DESCRIPTION), 156)
        status, _, body = self.get('/')
        self.assertEqual(status, 200)
        self.assertIn('<meta name="description" content="' + DESCRIPTION + '">', body)
        self.assertIn('<meta property="og:description" content="' + DESCRIPTION + '">', body)
        self.assertIn('<meta property="og:title" content="VELXTRIA', body)
        self.assertIn('<meta property="og:type" content="website">', body)

    def test_robots_txt_is_public_and_blocks_private_paths(self):
        status, headers, body = self.get('/robots.txt')
        self.assertEqual(status, 200)
        self.assertIn('text/plain', headers.get('Content-Type', ''))
        self.assertIn('User-agent: *', body)
        self.assertIn('Allow: /', body)
        self.assertIn('Allow: /about', body)
        for blocked in ('/report', '/founder-stats', '/login', '/signup',
                        '/account', '/download'):
            self.assertIn('Disallow: ' + blocked, body)
        self.assertIn('Sitemap: http://127.0.0.1:%d/sitemap.xml' % self.port, body)

    def test_sitemap_lists_only_public_pages(self):
        status, headers, body = self.get('/sitemap.xml')
        self.assertEqual(status, 200)
        self.assertIn('application/xml', headers.get('Content-Type', ''))
        base = 'http://127.0.0.1:%d' % self.port
        self.assertIn('<loc>' + base + '/</loc>', body)
        self.assertIn('<loc>' + base + '/about</loc>', body)
        self.assertNotIn('/report', body)
        self.assertNotIn('/founder-stats', body)
        self.assertNotIn('/login', body)


if __name__ == '__main__':
    unittest.main()
