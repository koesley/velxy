"""Tests for the win-back drafts: the growth agent's first real work.

A draft is only ever written from the business's own ledger — the
customer's name, their last service, when it was, and what they are
worth. The tests pin the draft text, the richest-first order, the
90-day quiet rule, the dashboard panel, and the top draft riding
along in the weekly money-report email. Nothing here sends anything
to a customer: VELXTRIA holds no customer email addresses.

Run with:
  python -m unittest test_winback -v
"""
import http.client
import os
import re
import tempfile
import threading
import unittest
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from unittest.mock import patch

_TMP = None
_ENV = None

PASSWORD = 'WinbackDraft123456!'

_EMAIL_N = [0]


def fresh_email():
    _EMAIL_N[0] += 1
    return 'winback-%d@example.com' % _EMAIL_N[0]


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
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


def tearDownModule():
    import portal
    _ENV.stop()
    _TMP.cleanup()
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


# Fixed "now": Tuesday Nov 24, 2026, 12:00 UTC. The quiet cutoff is
# Aug 26, 2026 (90 days back).
NOW = int(datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc).timestamp())


def sale(order_id, order_date, customer, product, quantity, unit_price,
         status='Paid'):
    return {'order_id': order_id, 'order_date': order_date,
            'customer': customer, 'product': product,
            'quantity': str(quantity), 'unit_price': unit_price,
            'status': status, 'region': 'Louisville'}


class WinbackTests(unittest.TestCase):
    def setUp(self):
        import portal
        self.portal = portal
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), portal.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.port = self.server.server_address[1]

    def request(self, method, path, body=b'', content_type=None,
                headers=None):
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

    def signed_in(self):
        email = fresh_email()
        status, _, _ = self.post_form('/register', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        status, headers, _ = self.post_form('/login', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        session = [p for p in headers['Set-Cookie'].split(',')
                   if 'velxtria_session=' in p][0].split(';')[0]
        headers = {'Cookie': session}
        with self.portal.db() as c:
            uid = c.execute(
                'SELECT id FROM users WHERE email=?', (email,)).fetchone()[0]
        return email, uid, headers

    def add_sale(self, uid, entry):
        import ledger
        with self.portal.db() as c:
            ledger.add_entry(c, uid, entry['order_id'],
                             entry['order_date'], entry['customer'],
                             entry['product'], entry['quantity'],
                             entry['unit_price'], entry['status'],
                             entry['region'])

    def test_draft_uses_real_data(self):
        import winback
        _, uid, _ = self.signed_in()
        self.add_sale(uid, sale('W-001', '2026-11-23', 'Ann',
                                'Deep Cleaning', 4, '90.00'))
        self.add_sale(uid, sale('W-002', '2026-08-10', 'Mrs. Johnson',
                                'Deep Cleaning', 1, '250.00'))
        with self.portal.db() as c:
            found = winback.drafts(c, uid, now=NOW)
        self.assertEqual(len(found), 1)
        draft = found[0]
        self.assertEqual(draft['customer'], 'Mrs. Johnson')
        self.assertEqual(draft['days_quiet'], 106)
        self.assertEqual(str(draft['lifetime']), '250.00')
        self.assertEqual(draft['last_product'], 'Deep Cleaning')
        self.assertIn('Mrs. Johnson', draft['text'])
        self.assertIn('Deep Cleaning', draft['text'])
        self.assertIn('Aug 10', draft['text'])
        self.assertIn('$250.00', draft['text'])
        # No discount promised, no urgency invented.
        self.assertNotIn('%', draft['text'])
        self.assertNotIn('discount', draft['text'].lower())
        self.assertNotIn('running out', draft['text'].lower())

    def test_richest_quiet_customer_first(self):
        import winback
        _, uid, _ = self.signed_in()
        self.add_sale(uid, sale('W-101', '2026-08-10', 'Mrs. Johnson',
                                'Deep Cleaning', 1, '250.00'))
        self.add_sale(uid, sale('W-102', '2026-07-01', 'Mr. Big',
                                'Gutter Cleaning', 4, '100.00'))
        with self.portal.db() as c:
            found = winback.drafts(c, uid, now=NOW)
        self.assertEqual([d['customer'] for d in found],
                         ['Mr. Big', 'Mrs. Johnson'])

    def test_no_draft_for_recent_customers(self):
        import winback
        _, uid, _ = self.signed_in()
        self.add_sale(uid, sale('W-201', '2026-11-23', 'Ann',
                                'Deep Cleaning', 4, '90.00'))
        with self.portal.db() as c:
            self.assertEqual(winback.drafts(c, uid, now=NOW), [])

    def test_empty_ledger_no_drafts(self):
        import winback
        _, uid, _ = self.signed_in()
        with self.portal.db() as c:
            self.assertEqual(winback.drafts(c, uid, now=NOW), [])

    def test_dashboard_shows_winback_drafts(self):
        # Dates relative to the real current week, so this holds on any
        # day the suite runs.
        today = datetime.now(timezone.utc).date()
        monday = today - timedelta(days=today.weekday())
        _, uid, headers = self.signed_in()
        self.add_sale(uid, sale('D-101', (monday + timedelta(days=1)
                                          ).isoformat(), 'Ann',
                                'Deep Cleaning', 4, '90.00'))
        self.add_sale(uid, sale('D-102', (today - timedelta(days=100)
                                          ).isoformat(), 'Mrs. Johnson',
                                'Deep Cleaning', 1, '250.00'))
        _, _, text = self.get('/', headers=headers)
        self.assertIn('Win-back drafts', text)
        self.assertIn('Mrs. Johnson', text)
        self.assertIn('$250.00', text)
        self.assertIn('book your next Deep Cleaning', text)
        self.assertIn('Deep Cleaning: $360.00 (1 order)', text)

    def test_dashboard_no_quiet_customers(self):
        today = datetime.now(timezone.utc).date()
        monday = today - timedelta(days=today.weekday())
        _, uid, headers = self.signed_in()
        self.add_sale(uid, sale('D-201', (monday + timedelta(days=1)
                                          ).isoformat(), 'Ann',
                                'Deep Cleaning', 4, '90.00'))
        _, _, text = self.get('/', headers=headers)
        self.assertIn('Win-back drafts', text)
        self.assertIn('No one has gone quiet', text)

    def test_weekly_email_carries_top_draft(self):
        import followups
        email, uid, _ = self.signed_in()
        self.add_sale(uid, sale('E-001', '2026-11-23', 'Ann',
                                'Deep Cleaning', 4, '90.00'))
        self.add_sale(uid, sale('E-002', '2026-08-10', 'Mrs. Johnson',
                                'Deep Cleaning', 1, '250.00'))
        with self.portal.db() as c:
            self.assertEqual(
                followups.queue_weekly_money_report(
                    c, uid, email, 'https://example.test', now=NOW), 1)
            row = c.execute(
                "SELECT body FROM email_outbox WHERE kind='money_report'"
                ' AND recipient=?', (email,)).fetchone()
        self.assertIn('WIN-BACK DRAFT', row[0])
        self.assertIn('Mrs. Johnson', row[0])
        self.assertIn('book your next Deep Cleaning', row[0])

    def test_mark_sent_records_and_is_idempotent(self):
        import winback
        _, uid, _ = self.signed_in()
        self.add_sale(uid, sale('T-001', '2026-11-23', 'Ann',
                                'Deep Cleaning', 4, '90.00'))
        self.add_sale(uid, sale('T-002', '2026-08-10', 'Mrs. Johnson',
                                'Deep Cleaning', 1, '250.00'))
        with self.portal.db() as c:
            first = winback.mark_sent(c, uid, 'Mrs. Johnson', now=NOW)
            second = winback.mark_sent(c, uid, 'Mrs. Johnson', now=NOW)
            self.assertEqual(first, second)
            rows = c.execute(
                'SELECT COUNT(*) FROM winback_sends WHERE user_id=?',
                (uid,)).fetchone()[0]
            self.assertEqual(rows, 1)
            found = winback.drafts(c, uid, now=NOW)
        self.assertEqual(len(found), 1)
        self.assertIsNotNone(found[0]['sent_at'])

    def test_mark_sent_rejects_non_quiet(self):
        import winback
        _, uid, _ = self.signed_in()
        self.add_sale(uid, sale('T-101', '2026-11-23', 'Ann',
                                'Deep Cleaning', 4, '90.00'))
        self.add_sale(uid, sale('T-102', '2026-08-10', 'Mrs. Johnson',
                                'Deep Cleaning', 1, '250.00'))
        with self.portal.db() as c:
            with self.assertRaises(ValueError):
                winback.mark_sent(c, uid, 'Ann', now=NOW)
            with self.assertRaises(ValueError):
                winback.mark_sent(c, uid, 'Nobody Here', now=NOW)

    def test_recovery_counts_returned_customer(self):
        import winback
        from decimal import Decimal
        _, uid, _ = self.signed_in()
        self.add_sale(uid, sale('T-201', '2026-08-10', 'Mrs. Johnson',
                                'Deep Cleaning', 1, '250.00'))
        with self.portal.db() as c:
            winback.mark_sent(c, uid, 'Mrs. Johnson', now=NOW)
            # The Aug 10 order predates the send: not a recovery.
            self.assertEqual(winback.recovery(c, uid, now=NOW),
                             (1, 0, Decimal('0')))
        # She books again after the send: recovered.
        self.add_sale(uid, sale('T-202', '2026-11-25', 'Mrs. Johnson',
                                'Deep Cleaning', 1, '120.00'))
        with self.portal.db() as c:
            self.assertEqual(winback.recovery(c, uid, now=NOW),
                             (1, 1, Decimal('120.00')))

    def test_dashboard_mark_as_sent_flow(self):
        today = datetime.now(timezone.utc).date()
        monday = today - timedelta(days=today.weekday())
        _, uid, headers = self.signed_in()
        self.add_sale(uid, sale('T-301', (monday + timedelta(days=1)
                                          ).isoformat(), 'Ann',
                                'Deep Cleaning', 4, '90.00'))
        self.add_sale(uid, sale('T-302', (today - timedelta(days=100)
                                          ).isoformat(), 'Mrs. Johnson',
                                'Deep Cleaning', 1, '250.00'))
        _, _, text = self.get('/', headers=headers)
        self.assertIn('Mark as sent', text)
        csrf = re.search(r'name="csrf" value="([^"]+)"', text).group(1)
        status, _, _ = self.post_form('/winback/sent', {
            'csrf': csrf, 'customer': 'Mrs. Johnson'}, headers=headers)
        self.assertEqual(status, 303)
        _, _, text = self.get('/', headers=headers)
        self.assertNotIn('Mark as sent', text)
        self.assertIn('Sent ', text)
        self.assertIn('Win-backs sent: 1', text)
        self.assertIn('Customers back: 0', text)

    def test_money_report_shows_recovery(self):
        import followups
        email, uid, _ = self.signed_in()
        self.add_sale(uid, sale('T-401', '2026-11-23', 'Ann',
                                'Deep Cleaning', 4, '90.00'))
        self.add_sale(uid, sale('T-402', '2026-08-10', 'Mrs. Johnson',
                                'Deep Cleaning', 1, '250.00'))
        with self.portal.db() as c:
            import winback
            winback.mark_sent(c, uid, 'Mrs. Johnson', now=NOW)
        self.add_sale(uid, sale('T-403', '2026-11-25', 'Mrs. Johnson',
                                'Deep Cleaning', 1, '120.00'))
        # Sign in again for a fresh session cookie.
        status, hdrs, _ = self.post_form('/login', {
            'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        session = [p for p in hdrs['Set-Cookie'].split(',')
                   if 'velxtria_session=' in p][0].split(';')[0]
        _, _, text = self.get('/', headers={'Cookie': session})
        self.assertIn('Win-backs sent: 1', text)
        self.assertIn('Customers back: 1', text)
        self.assertIn('$120.00 recovered', text)
        with self.portal.db() as c:
            row = c.execute(
                "SELECT body FROM email_outbox WHERE kind='money_report'"
                ' AND recipient=?', (email,)).fetchone()
        self.assertIn('WIN-BACK RESULTS', row[0])
        self.assertIn('Customers back: 1', row[0])
        self.assertIn('$120.00', row[0])

    def test_winback_sql_is_postgres_portable(self):
        # Win-back drafts read through money_report only — keep
        # SQLite-only statements out of this module too.
        import winback
        import pathlib
        src = pathlib.Path(winback.__file__).read_text()
        self.assertNotIn('OR IGNORE', src)
        self.assertNotIn('OR REPLACE', src)


if __name__ == '__main__':
    unittest.main()
