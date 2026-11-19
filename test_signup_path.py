"""Tests for the sign-up path: /signup reaches registration, the login page
links visibly to registration, and a successful registration confirms itself
instead of silently dropping the new user at the login form.

A brand-new visitor used to hit /signup, land on /login, and find no way to
create an account — the only "Create demo account" link hid inside the
collapsed "Explore platform" nav menu. Run with:
  python -m unittest test_signup_path -v
"""
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


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
    emails = "('new@example.test','next@example.test','signin@example.test')"
    with portal.db() as c:
        c.execute(
            'DELETE FROM sessions WHERE user_id IN '
            '(SELECT id FROM users WHERE email IN %s)' % emails)
        c.execute('DELETE FROM users WHERE email IN %s' % emails)
    _ENV.stop()
    _TMP.cleanup()
    # Leave DATA_ROOT in place: later modules reuse the same imported
    # portal, and a deleted data dir breaks their DB access.
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class SignupPathTests(unittest.TestCase):
    def setUp(self):
        import portal
        self.portal = portal
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), portal.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.base = 'http://127.0.0.1:%d' % self.server.server_address[1]
        self.opener = urllib.request.build_opener(NoRedirect)

    def fetch(self, path, data=None):
        req = urllib.request.Request(self.base + path, data=data)
        try:
            with self.opener.open(req, timeout=30) as resp:
                return resp.status, dict(resp.headers), resp.read().decode('utf-8')
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read().decode('utf-8')

    def test_signup_redirects_to_register(self):
        status, headers, _ = self.fetch('/signup')
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/register')

    def test_signup_preserves_next_and_rejects_offsite_next(self):
        _, headers, _ = self.fetch('/signup?next=/about')
        self.assertEqual(headers.get('Location'), '/register?next=%2Fabout')
        _, headers, _ = self.fetch('/signup?next=https://evil.example.com')
        self.assertEqual(headers.get('Location'), '/register')

    def test_public_hero_exposes_free_registration(self):
        status, _, body = self.fetch('/')
        self.assertEqual(status, 200)
        self.assertIn('href="/register">CREATE FREE ACCOUNT', body)
        self.assertIn('href="#try">TRY IT NOW', body)
        self.assertIn('href="/login">SIGN IN', body)
        self.assertIn('PRO — $49 / 30 DAYS (BITCOIN)', body)

    def test_login_page_links_visibly_to_register(self):
        status, _, body = self.fetch('/login')
        self.assertEqual(status, 200)
        self.assertIn('Create a demo account', body)
        self.assertIn('href="/register"', body)

    def test_login_page_register_link_preserves_next(self):
        _, _, body = self.fetch('/login?next=/about')
        self.assertIn('href="/register?next=%2Fabout"', body)

    def test_login_page_shows_created_banner_only_with_flag(self):
        _, _, body = self.fetch('/login?registered=1')
        self.assertIn('Account created', body)
        _, _, plain = self.fetch('/login')
        self.assertNotIn('Account created', plain)

    def test_register_page_links_back_to_login(self):
        status, _, body = self.fetch('/register')
        self.assertEqual(status, 200)
        self.assertIn('href="/login"', body)
        self.assertIn('Already have an account?', body)

    def test_register_post_redirects_to_login_with_registered_flag(self):
        data = urllib.parse.urlencode({
            'email': 'new@example.test',
            'password': 'TestPass123456!',
        }).encode()
        status, headers, _ = self.fetch('/register', data=data)
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/login?registered=1')
        status, _, body = self.fetch('/login?registered=1')
        self.assertEqual(status, 200)
        self.assertIn('Account created', body)

    def test_register_post_preserves_next_after_flag(self):
        data = urllib.parse.urlencode({
            'email': 'next@example.test',
            'password': 'TestPass123456!',
            'next': '/about',
        }).encode()
        status, headers, _ = self.fetch('/register', data=data)
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/login?registered=1&next=%2Fabout')

    def test_registered_account_can_sign_in(self):
        data = urllib.parse.urlencode({
            'email': 'signin@example.test',
            'password': 'TestPass123456!',
        }).encode()
        self.fetch('/register', data=data)
        status, headers, _ = self.fetch('/login', data=data)
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/')
        self.assertIn('velxtria_session=', headers.get('Set-Cookie', ''))


if __name__ == '__main__':
    unittest.main()
