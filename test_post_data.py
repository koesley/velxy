"""Tests for post_data() request-size errors: an empty POST must say so,
instead of blaming the upload size.

An empty POST body (Content-Length 0, e.g. a client re-posting to a
redirect target) used to come back as 400 "Upload too large (maximum
5 MB)", which sent debugging down the wrong path entirely. Run with:
  python -m unittest test_post_data -v
"""
import http.client
import os
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


class PostDataTests(unittest.TestCase):
    def setUp(self):
        import portal
        self.portal = portal
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), portal.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.port = self.server.server_address[1]

    def post(self, path, body=b''):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
        try:
            conn.request('POST', path, body=body, headers={
                'Content-Type': 'application/x-www-form-urlencoded'})
            resp = conn.getresponse()
            return resp.status, resp.read().decode('utf-8')
        finally:
            conn.close()

    def test_empty_post_says_empty_not_too_large(self):
        status, body = self.post('/login', body=b'')
        self.assertEqual(status, 400)
        self.assertIn('Empty request', body)
        self.assertNotIn('Upload too large', body)

    def test_oversized_post_still_says_too_large(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
        try:
            # Claim a body just over the limit without sending it: the
            # server rejects on Content-Length before reading any body.
            conn.putrequest('POST', '/login')
            conn.putheader('Content-Length',
                           str(self.portal.MAX_BYTES + 65537))
            conn.putheader('Content-Type',
                           'application/x-www-form-urlencoded')
            conn.endheaders()
            resp = conn.getresponse()
            body = resp.read().decode('utf-8')
        finally:
            conn.close()
        self.assertEqual(resp.status, 400)
        self.assertIn('Upload too large (maximum 5 MB)', body)

    def test_normal_post_still_reaches_handler(self):
        body = urllib.parse.urlencode({
            'email': 'nobody@example.test',
            'password': 'TestPass123456!',
        }).encode()
        status, text = self.post('/login', body=body)
        self.assertEqual(status, 401)
        self.assertIn('Invalid email or password', text)


if __name__ == '__main__':
    unittest.main()
