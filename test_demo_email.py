"""Tests for demo lead capture: the "Email me this report" form on the
instant-demo result page and the public share page emails the demo's
summaries to the runner and records the lead, so anonymous demo runners
can be reached again instead of vanishing. Run with:
  python -m unittest test_demo_email -v
"""
import http.client
import os
import re
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.parse
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import demo_leads
import demo_shares

_TMP = None
_ENV = None
_EMAIL_N = [0]


def _unique_email(prefix):
    _EMAIL_N[0] += 1
    return '%s%d@example.test' % (prefix, _EMAIL_N[0])

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


class DemoLeadUnitTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        demo_leads.setup(self.conn)

    def test_first_record_claims_and_repeat_is_a_noop(self):
        self.assertTrue(demo_leads.record(self.conn, 'a@example.test', 'tok1'))
        self.assertFalse(demo_leads.record(self.conn, 'a@example.test', 'tok1'))
        rows = self.conn.execute(
            'SELECT COUNT(*) FROM demo_leads WHERE email=?',
            ('a@example.test',)).fetchone()[0]
        self.assertEqual(rows, 1)

    def test_same_email_may_receive_different_demos(self):
        self.assertTrue(demo_leads.record(self.conn, 'a@example.test', 'tok1'))
        self.assertTrue(demo_leads.record(self.conn, 'a@example.test', 'tok2'))

    def test_daily_cap_blocks_a_fourth_demo(self):
        for n in range(3):
            self.assertTrue(
                demo_leads.record(self.conn, 'a@example.test', 'tok%d' % n))
        self.assertFalse(
            demo_leads.record(self.conn, 'a@example.test', 'tok3'))
        # A different address is unaffected by the cap.
        self.assertTrue(demo_leads.record(self.conn, 'b@example.test', 'tok3'))

    def test_cap_rolls_off_after_a_day(self):
        old = int(time.time()) - demo_leads.DAY - 60
        for n in range(3):
            self.assertTrue(demo_leads.record(
                self.conn, 'a@example.test', 'tok%d' % n, now=old))
        self.assertTrue(demo_leads.record(self.conn, 'a@example.test', 'tok3'))

    def test_email_body_has_summaries_link_and_signup(self):
        body = demo_leads.format_email_body(
            SAMPLE_REPORT, 'https://example.test/demo/tok1',
            'https://example.test')
        self.assertIn('$350.00', body)
        self.assertIn('Window Cleaning', body)
        self.assertIn('https://example.test/demo/tok1', body)
        self.assertIn('https://example.test/register', body)
        self.assertNotIn('X-001', body)
        self.assertNotIn('Secret Customer', body)


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


class DemoEmailFlowTests(unittest.TestCase):
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

    def post_form(self, path, fields):
        body = urllib.parse.urlencode(fields).encode()
        status, headers, raw = self.request(
            'POST', path, body=body,
            content_type='application/x-www-form-urlencoded')
        return status, headers, raw.decode('utf-8', 'replace')

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
        match = re.search(r'/demo/(?!signup|email)([A-Za-z0-9_-]+)', body.decode('utf-8', 'replace'))
        self.assertTrue(match, 'demo result page has no share link')
        return body.decode('utf-8', 'replace'), match.group(1)

    def outbox_for(self, email):
        # Only the demo REPORT email: the revenue engine also queues 3
        # scheduled follow-ups per demo for the same address, and those
        # are verified separately in test_revenue_engine.
        with self.portal.db() as c:
            return c.execute(
                'SELECT subject,body,kind FROM email_outbox'
                " WHERE recipient=? AND kind='demo_report'",
                (email,)).fetchall()

    def lead_rows(self, email):
        with self.portal.db() as c:
            return c.execute(
                'SELECT share_token FROM demo_leads WHERE email=?',
                (email,)).fetchall()

    def event_count(self, event):
        with self.portal.db() as c:
            return c.execute(
                'SELECT COUNT(*) FROM site_events WHERE event=?',
                (event,)).fetchone()[0]

    def test_demo_result_page_has_email_form(self):
        body, token = self.run_demo()
        self.assertIn('action="/demo/email"', body)
        self.assertIn('name="share_token" value="%s"' % token, body)
        self.assertIn('Email me this report', body)

    def test_share_page_has_email_form(self):
        _, token = self.run_demo()
        status, _, body = self.get('/demo/' + token)
        self.assertEqual(status, 200)
        self.assertIn('action="/demo/email"', body)
        self.assertIn('name="share_token" value="%s"' % token, body)

    def test_emailing_report_queues_email_records_lead_and_event(self):
        _, token = self.run_demo()
        email = _unique_email('lead')
        status, _, body = self.post_form(
            '/demo/email', {'email': email, 'share_token': token})
        self.assertEqual(status, 200)
        self.assertIn('Check your email', body)
        rows = self.outbox_for(email)
        self.assertEqual(len(rows), 1)
        subject, mail_body, kind = rows[0]
        self.assertEqual(kind, 'demo_report')
        self.assertIn('demo report', subject.lower())
        self.assertIn('/demo/' + token, mail_body)
        self.assertIn('$350.00', mail_body)
        self.assertIn('Window Cleaning', mail_body)
        self.assertIn('/register', mail_body)
        self.assertNotIn('X-001', mail_body)
        self.assertNotIn('Secret Customer', mail_body)
        self.assertEqual(self.lead_rows(email), [(token,)])
        self.assertGreaterEqual(self.event_count('demo_email_sent'), 1)

    def test_duplicate_submit_sends_only_once(self):
        _, token = self.run_demo()
        email = _unique_email('dup')
        status, _, _ = self.post_form(
            '/demo/email', {'email': email, 'share_token': token})
        self.assertEqual(status, 200)
        status, _, _ = self.post_form(
            '/demo/email', {'email': email, 'share_token': token})
        self.assertEqual(status, 200)
        self.assertEqual(len(self.outbox_for(email)), 1)
        self.assertEqual(len(self.lead_rows(email)), 1)

    def test_daily_cap_stops_a_fourth_demo_email(self):
        email = _unique_email('cap')
        tokens = [self.run_demo()[1] for _ in range(4)]
        for token in tokens[:3]:
            status, _, _ = self.post_form(
                '/demo/email', {'email': email, 'share_token': token})
            self.assertEqual(status, 200)
        self.assertEqual(len(self.outbox_for(email)), 3)
        # The fourth is still a friendly confirmation — but nothing is sent.
        status, _, body = self.post_form(
            '/demo/email', {'email': email, 'share_token': tokens[3]})
        self.assertEqual(status, 200)
        self.assertIn('Check your email', body)
        self.assertEqual(len(self.outbox_for(email)), 3)
        self.assertEqual(len(self.lead_rows(email)), 3)

    def test_invalid_email_and_unknown_token(self):
        _, token = self.run_demo()
        status, _, _ = self.post_form(
            '/demo/email', {'email': 'not-an-email', 'share_token': token})
        self.assertEqual(status, 400)
        status, _, _ = self.post_form(
            '/demo/email', {'email': 'a@example.test', 'share_token': 'no-such-token'})
        self.assertEqual(status, 404)
        status, _, _ = self.post_form(
            '/demo/email', {'email': 'a@example.test', 'share_token': ''})
        self.assertEqual(status, 404)


if __name__ == '__main__':
    unittest.main()
