"""Regression coverage for the public browser-only CSV readiness workflow."""
import unittest
from unittest.mock import patch
import csv_readiness


class CSVReadinessTests(unittest.TestCase):
    def test_uses_real_required_headers(self):
        import portal
        page = csv_readiness.page(portal.REQUIRED, portal.MAX_BYTES)
        for header in portal.REQUIRED:
            self.assertIn(header, page)
        self.assertIn(str(portal.MAX_BYTES), page)

    def test_no_network_or_storage_in_checker(self):
        page = csv_readiness.page(['Order ID'])
        self.assertIn('file.text()', page)
        self.assertIn('replaceChildren()', page)
        self.assertNotIn('fetch(', page)
        self.assertNotIn('XMLHttpRequest', page)
        self.assertNotIn('localStorage', page)
        self.assertNotIn('innerHTML', page)

    def test_parser_handles_quoted_fields_and_malformed_csv(self):
        page = csv_readiness.page(['Order ID'])
        self.assertIn("source[i + 1] === '", page)
        self.assertIn('Unclosed quoted field', page)
        self.assertIn('Unexpected text after a quoted field', page)
        self.assertIn('different number of columns', page)

    def test_rejects_missing_headers_and_duplicate_columns(self):
        page = csv_readiness.page(['Order ID'])
        self.assertIn('Missing headers:', page)
        self.assertIn('Duplicate column names:', page)
        self.assertIn('Fix the listed issues', page)

    def test_escapes_script_termination_in_dynamic_header(self):
        page = csv_readiness.page(['</script><script>alert(1)</script>'])
        self.assertNotIn('</script><script>alert(1)</script>', page)
        self.assertIn('const required =', page)

    def test_invalid_header_configuration_fails_closed(self):
        with self.assertRaises(ValueError):
            csv_readiness.page([])
        with self.assertRaises(ValueError):
            csv_readiness.page([''])

    def test_landing_and_public_route_are_connected(self):
        import portal
        self.assertIn('href="/csv-readiness"', portal.landing_page())
        import inspect
        self.assertIn("if p=='/csv-readiness':", inspect.getsource(portal.Handler.do_GET))
        self.assertIn('csv_readiness.page(REQUIRED,MAX_BYTES)', inspect.getsource(portal.Handler.do_GET))


if __name__ == '__main__':
    unittest.main()
