"""Tests for the weekly money report: what a business made, what to
push, who went quiet.

The report is the proof piece for the growth agent — it has to be
right, because a business will judge the agent by these numbers. So
every number in it is computed from the business's own ledger and
reports, and the tests pin the week split, the top-product order, the
90-day quiet rule, the win-back threshold, the once-per-week email
dedupe, and the dashboard rendering (including the empty state).

Run with:
  python -m unittest test_money_report -v
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

PASSWORD = 'MoneyReport123456!'

_EMAIL_N = [0]


def fresh_email():
    _EMAIL_N[0] += 1
    return 'money-report-%d@example.com' % _EMAIL_N[0]


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


# Fixed "now": Tuesday Nov 24, 2026, 12:00 UTC. This week starts
# Monday Nov 23; last week starts Monday Nov 16; the quiet cutoff is
# Aug 26, 2026 (90 days back).
NOW = int(datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc).timestamp())


def sale(order_id, order_date, customer, product, quantity, unit_price,
         status='Paid'):
    return {'order_id': order_id, 'order_date': order_date,
            'customer': customer, 'product': product,
            'quantity': str(quantity), 'unit_price': unit_price,
            'status': status, 'region': 'Louisville'}


class MoneyReportTests(unittest.TestCase):
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

    def seed_business(self, uid):
        """A cleaning business with a real week behind it: $360 of Deep
        Cleaning and $120 of Gutter this week, $180 last week, one
        $500 pending order that must not count, and Mrs. Johnson, who
        last paid $250 on Aug 10 and has gone quiet."""
        self.add_sale(uid, sale('M-001', '2026-11-23', 'Ann',
                                'Deep Cleaning', 4, '90.00'))
        self.add_sale(uid, sale('M-002', '2026-11-24', 'Bob',
                                'Gutter Cleaning', 1, '120.00'))
        self.add_sale(uid, sale('M-003', '2026-11-18', 'Ann',
                                'Deep Cleaning', 2, '90.00'))
        self.add_sale(uid, sale('M-004', '2026-11-24', 'Cid',
                                'Deep Cleaning', 5, '100.00',
                                status='Pending'))
        self.add_sale(uid, sale('M-005', '2026-08-10', 'Mrs. Johnson',
                                'Deep Cleaning', 1, '250.00'))

    def test_empty_business_has_no_data(self):
        import money_report
        _, uid, _ = self.signed_in()
        with self.portal.db() as c:
            report = money_report.weekly_report(c, uid, now=NOW)
        self.assertFalse(report['has_data'])
        self.assertEqual(report['revenue_this_week'], 0)
        self.assertEqual(report['orders_this_week'], 0)
        self.assertEqual(report['top_products'], [])
        self.assertEqual(report['quiet_customers'], [])
        self.assertIsNone(report['latest_report'])
        self.assertIn('Nothing in your ledger yet', report['top_move'])

    def test_report_without_ledger_is_still_empty(self):
        # A report alone is not sales: a user who claimed the sample
        # demo's report has nothing in their ledger, so the money
        # report stays empty and no weekly email is queued. This is
        # the regression for the sample-demo signup, whose dashboard
        # must never claim sales were logged.
        import money_report
        import followups
        email, uid, headers = self.signed_in()
        with self.portal.db() as c:
            c.execute(
                'INSERT INTO reports'
                ' (id,user_id,filename,created,status,accepted,rejected,'
                'digest) VALUES (?,?,?,?,?,?,?,?)',
                ('sample-report', uid, 'VELXTRIA_Sample_Sales.csv', NOW,
                 'ready', 6, 3, 'x'))
            report = money_report.weekly_report(c, uid, now=NOW)
            self.assertFalse(report['has_data'])
            self.assertEqual(report['latest_report'], (6, 3))
            self.assertEqual(
                followups.queue_weekly_money_report(
                    c, uid, email, 'https://example.test', now=NOW), 0)
        _, _, text = self.get('/', headers=headers)
        self.assertIn('Your money report', text)
        self.assertIn('Nothing in your ledger yet', text)
        self.assertNotIn('sales logged', text)

    def test_week_split_and_top_products(self):
        import money_report
        from decimal import Decimal
        _, uid, _ = self.signed_in()
        self.seed_business(uid)
        with self.portal.db() as c:
            report = money_report.weekly_report(c, uid, now=NOW)
        self.assertTrue(report['has_data'])
        # This week: $360 + $120; the $500 pending order does not count.
        self.assertEqual(report['revenue_this_week'], Decimal('480.00'))
        self.assertEqual(report['orders_this_week'], 2)
        self.assertEqual(report['revenue_last_week'], Decimal('180.00'))
        self.assertEqual(report['orders_last_week'], 1)
        self.assertEqual(report['top_products'][0],
                         ('Deep Cleaning', 1, Decimal('360.00')))
        self.assertEqual(report['top_products'][1],
                         ('Gutter Cleaning', 1, Decimal('120.00')))

    def test_quiet_customer_and_win_back_move(self):
        import money_report
        _, uid, _ = self.signed_in()
        self.seed_business(uid)
        with self.portal.db() as c:
            report = money_report.weekly_report(c, uid, now=NOW)
        # Mrs. Johnson last paid Aug 10 — 106 days before Nov 24.
        self.assertEqual(len(report['quiet_customers']), 1)
        name, days, lifetime, last = report['quiet_customers'][0]
        self.assertEqual(name, 'Mrs. Johnson')
        self.assertEqual(days, 106)
        self.assertEqual(str(lifetime), '250.00')
        self.assertEqual(last, '2026-08-10')
        # Worth $250, over the $100 win-back bar, so she is the top move.
        self.assertIn('Win back Mrs. Johnson', report['top_move'])
        self.assertIn('$250.00', report['top_move'])

    def test_small_quiet_customer_yields_product_move(self):
        import money_report
        _, uid, _ = self.signed_in()
        self.add_sale(uid, sale('S-001', '2026-11-23', 'Ann',
                                'Deep Cleaning', 4, '90.00'))
        self.add_sale(uid, sale('S-002', '2026-08-10', 'Mr. Smith',
                                'Gutter Cleaning', 1, '40.00'))
        with self.portal.db() as c:
            report = money_report.weekly_report(c, uid, now=NOW)
        self.assertEqual(len(report['quiet_customers']), 1)
        self.assertIn('Push Deep Cleaning', report['top_move'])
        self.assertIn('$360.00', report['top_move'])

    def test_email_body_is_real_numbers_only(self):
        import money_report
        _, uid, _ = self.signed_in()
        self.seed_business(uid)
        with self.portal.db() as c:
            report = money_report.weekly_report(c, uid, now=NOW)
        body = money_report.report_email_body(
            report, 'https://example.test')
        self.assertIn('$480.00', body)
        self.assertIn('$180.00', body)
        self.assertIn('Deep Cleaning: $360.00 (1 order)', body)
        self.assertIn('Mrs. Johnson', body)
        self.assertIn('https://example.test/', body)
        # The agent does not exist yet: the report never claims it sent
        # a follow-up or brought anyone back.
        self.assertNotIn('I sent', body)
        self.assertNotIn('brought back', body)
        self.assertEqual(money_report.report_email_subject(report),
                         'Your money report: $480.00 this week')

    def test_weekly_email_queued_once_per_week(self):
        import followups
        email, uid, _ = self.signed_in()
        self.seed_business(uid)
        with self.portal.db() as c:
            self.assertEqual(
                followups.queue_weekly_money_report(
                    c, uid, email, 'https://example.test', now=NOW), 1)
            # Same week again: deduped.
            self.assertEqual(
                followups.queue_weekly_money_report(
                    c, uid, email, 'https://example.test', now=NOW), 0)
            # Next week: a fresh report.
            self.assertEqual(
                followups.queue_weekly_money_report(
                    c, uid, email, 'https://example.test',
                    now=NOW + 7 * 86400), 1)
            rows = c.execute(
                "SELECT subject FROM email_outbox WHERE kind='money_report'"
                ' AND recipient=?', (email,)).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], 'Your money report: $480.00 this week')

    def test_weekly_email_skipped_with_no_data(self):
        import followups
        email, uid, _ = self.signed_in()
        with self.portal.db() as c:
            self.assertEqual(
                followups.queue_weekly_money_report(
                    c, uid, email, 'https://example.test', now=NOW), 0)
            rows = c.execute(
                "SELECT 1 FROM email_outbox WHERE kind='money_report'"
                ' AND recipient=?', (email,)).fetchall()
        self.assertEqual(rows, [])

    def test_dashboard_shows_money_report(self):
        # Dates relative to the real current week, so this holds on any
        # day the suite runs: two paid sales this week, one last week,
        # one quiet customer worth $250.
        today = datetime.now(timezone.utc).date()
        monday = today - timedelta(days=today.weekday())
        email, uid, headers = self.signed_in()
        self.add_sale(uid, sale('D-001', (monday + timedelta(days=1)
                                          ).isoformat(), 'Ann',
                                'Deep Cleaning', 4, '90.00'))
        self.add_sale(uid, sale('D-002', (monday + timedelta(days=2)
                                          ).isoformat(), 'Bob',
                                'Gutter Cleaning', 1, '120.00'))
        self.add_sale(uid, sale('D-003', (monday - timedelta(days=3)
                                          ).isoformat(), 'Ann',
                                'Deep Cleaning', 2, '90.00'))
        self.add_sale(uid, sale('D-004', (today - timedelta(days=100)
                                          ).isoformat(), 'Mrs. Johnson',
                                'Deep Cleaning', 1, '250.00'))
        _, _, text = self.get('/', headers=headers)
        self.assertIn('Your money report', text)
        self.assertIn('$480.00', text)
        self.assertIn('Deep Cleaning', text)
        self.assertIn('Win back Mrs. Johnson', text)
        # The dashboard visit queued this week's email.
        with self.portal.db() as c:
            rows = c.execute(
                "SELECT subject FROM email_outbox WHERE kind='money_report'"
                ' AND recipient=?', (email,)).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertIn('$480.00', rows[0][0])

    def test_dashboard_empty_state(self):
        _, _, headers = self.signed_in()
        _, _, text = self.get('/', headers=headers)
        self.assertIn('Your money report', text)
        self.assertIn('Nothing in your ledger yet', text)

    def test_money_report_sql_is_postgres_portable(self):
        # Regression guard: the register 502 came from SQLite-only
        # INSERT OR IGNORE in a module that runs against Postgres.
        # The money report only reads, and its queue path reuses the
        # portable ON CONFLICT upsert in notifications.queue — keep
        # SQLite-only statements out of both modules.
        import money_report
        import followups
        import pathlib
        for module in (money_report, followups):
            src = pathlib.Path(module.__file__).read_text()
            self.assertNotIn('OR IGNORE', src)
            self.assertNotIn('OR REPLACE', src)


if __name__ == '__main__':
    unittest.main()
