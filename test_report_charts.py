"""Tests for inline SVG revenue charts on report summaries: the demo
result, share page, report view and landing sample all show a monthly
revenue bar chart and a product revenue bar chart above the tables, so
the product itself looks like next-level tech instead of a spreadsheet.
Run with:
  python -m unittest test_report_charts -v
"""
import http.client
import os
import re
import tempfile
import threading
import unittest
import urllib.parse
from decimal import Decimal
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import charts

_TMP = None
_ENV = None

TEST_CSV = (
    b'Order ID,Order Date,Customer,Product,Quantity,Unit Price,Status,Region\n'
    b'X-001,2026-10-03,Secret Customer,Window Cleaning,2,85.00,Paid,Louisville\n'
    b'X-002,2026-10-05,Secret Customer,Deep Cleaning,1,180.00,Paid,Louisville\n'
    b'X-003,not-a-date,Secret Customer,Gutter Cleaning,1,120.00,Paid,Louisville\n'
)

MONTHLY = [['Month', 'Paid Orders', 'Paid Revenue'],
           ['2026-10', '3', '470.00'], ['2026-11', '2', '330.00']]
PRODUCT = [['Product', 'Paid Orders', 'Paid Revenue'],
           ['Window Cleaning', '1', '170.00'],
           ['Deep Cleaning', '2', '360.00'],
           ['Gutter Cleaning', '1', '120.00']]


class ChartUnitTests(unittest.TestCase):
    def test_monthly_chart_has_bars_values_and_month_labels(self):
        svg = charts.monthly_chart(MONTHLY)
        self.assertIn('<svg', svg)
        self.assertIn('Oct 26', svg)
        self.assertIn('Nov 26', svg)
        self.assertIn('$470', svg)
        self.assertIn('$330', svg)
        # One bar per month.
        self.assertEqual(svg.count('<rect'), 2)

    def test_product_chart_sorts_by_revenue_and_labels_values(self):
        svg = charts.product_chart(PRODUCT)
        self.assertIn('<svg', svg)
        # Highest revenue first: Deep Cleaning before Window Cleaning.
        self.assertLess(svg.index('Deep Cleaning'), svg.index('Window Cleaning'))
        self.assertIn('$360', svg)
        self.assertIn('$170', svg)
        self.assertIn('$120', svg)
        self.assertEqual(svg.count('<rect'), 3)

    def test_labels_are_escaped(self):
        rows = [['Product', 'Paid Orders', 'Paid Revenue'],
                ['<img src=x onerror=alert(1)>', '1', '100.00']]
        svg = charts.product_chart(rows)
        self.assertNotIn('<img src=x', svg)
        self.assertIn('&lt;img', svg)

    def test_no_data_renders_nothing(self):
        self.assertEqual(charts.monthly_chart([]), '')
        self.assertEqual(charts.product_chart([]), '')
        self.assertEqual(charts.monthly_chart([['Month', 'Paid Revenue']]), '')
        self.assertEqual(charts.product_chart([['Product', 'Paid Revenue']]), '')

    def test_unparseable_rows_are_skipped(self):
        rows = [['Month', 'Paid Orders', 'Paid Revenue'],
                ['2026-10', '3', 'not-a-number'],
                ['2026-11', '2', '330.00']]
        svg = charts.monthly_chart(rows)
        self.assertIn('Nov 26', svg)
        self.assertNotIn('Oct 26', svg)
        self.assertEqual(svg.count('<rect'), 1)

    def test_many_months_capped_and_many_products_capped(self):
        months = [['Month', 'Paid Orders', 'Paid Revenue']] + [
            ['2026-%02d' % m, '1', '100.00'] for m in range(1, 13)] + [
            ['2027-01', '1', '100.00']]
        svg = charts.monthly_chart(months)
        self.assertEqual(svg.count('<rect'), charts.MAX_MONTHS)
        products = [['Product', 'Paid Orders', 'Paid Revenue']] + [
            ['Product %d' % n, '1', '%d.00' % (n * 10)] for n in range(1, 12)]
        svg = charts.product_chart(products)
        self.assertEqual(svg.count('<rect'), charts.MAX_PRODUCTS)
        # Only the top 8 by revenue survive: Product 11 down to Product 4.
        self.assertIn('Product 11', svg)
        self.assertNotIn('Product 3', svg)

    def test_money_trims_whole_dollars(self):
        self.assertEqual(charts._money(Decimal('470.00')), '$470')
        self.assertEqual(charts._money(Decimal('470.50')), '$470.50')


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


class ChartFlowTests(unittest.TestCase):
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
        text = body.decode('utf-8', 'replace')
        match = re.search(r'/demo/(?!signup|email)([A-Za-z0-9_-]+)', text)
        self.assertTrue(match, 'demo result page has no share link')
        return text, match.group(1)

    def assert_charts_present(self, body, revenue='$350'):
        # The 3-row test CSV yields $350.00 in Oct 26 (Deep Cleaning $180,
        # Window Cleaning $170); the landing sample's 9-row dataset yields
        # $470 in Oct. The revenue arg picks which one to expect.
        self.assertIn('Revenue by month', body)
        self.assertIn('Revenue by product', body)
        self.assertIn('<svg class="vx-chart"', body)
        self.assertIn('Oct 26', body)
        self.assertIn(revenue, body)

    def test_demo_result_page_has_charts(self):
        body, _ = self.run_demo()
        self.assert_charts_present(body)

    def test_share_page_has_charts(self):
        _, token = self.run_demo()
        status, _, body = self.get('/demo/' + token)
        self.assertEqual(status, 200)
        self.assert_charts_present(body)
        # Raw row values never appear on the public share page: anyone with
        # the link could read a stranger's customer names. (They DO appear
        # on the demo result page itself — the on-screen diagnosis shows the
        # uploader their own rows — and on the fictional landing sample.)
        self.assertNotIn('X-001', body)
        self.assertNotIn('Secret Customer', body)

    def test_landing_sample_report_has_charts(self):
        status, _, body = self.get('/')
        self.assertEqual(status, 200)
        self.assert_charts_present(body, revenue='$470')


if __name__ == '__main__':
    unittest.main()
