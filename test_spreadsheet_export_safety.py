"""Regression coverage for spreadsheet-safe generated CSV exports."""
import csv
import tempfile
import unittest
from pathlib import Path

from automate import spreadsheet_safe, write_csv


class SpreadsheetExportSafetyTests(unittest.TestCase):
    def test_formula_prefixes_are_escaped(self):
        for value in ('=1+1', '+SUM(A1:A2)', '-cmd', '@HYPERLINK("x")',
                      '  =2+2', '\t@danger', '\r\n+danger'):
            with self.subTest(value=value):
                self.assertEqual(spreadsheet_safe(value), "'" + value)

    def test_benign_text_and_numeric_values_are_preserved(self):
        for value in ('Window Cleaning', 'Paid', '123.45', '2026-11-19',
                      '', '   ', 10, 12.5, None):
            with self.subTest(value=value):
                self.assertEqual(spreadsheet_safe(value), value)

    def test_all_csv_columns_are_protected_and_source_unchanged(self):
        original = {'Product': '=HYPERLINK("https://example.test")',
                    'Region': '  @danger', 'Revenue': '25.00'}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'product_summary.csv'
            write_csv(path, ['Product', 'Region', 'Revenue'], [original])
            with path.open(newline='', encoding='utf-8-sig') as stream:
                records = list(csv.DictReader(stream))
        self.assertEqual(records, [{
            'Product': "'=HYPERLINK(\"https://example.test\")",
            'Region': "'  @danger", 'Revenue': '25.00'}])
        self.assertEqual(original['Product'][0], '=')

    def test_rejected_row_fields_are_escaped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'rejected_rows.csv'
            write_csv(path, ['Source Line', 'Customer', 'Issue(s)'], [
                {'Source Line': 2, 'Customer': '+CMD', 'Issue(s)': 'invalid date'}])
            with path.open(newline='', encoding='utf-8-sig') as stream:
                row = next(csv.DictReader(stream))
        self.assertEqual(row['Customer'], "'+CMD")
        self.assertEqual(row['Source Line'], '2')

    def test_extra_columns_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'output.csv'
            with self.assertRaises(ValueError):
                write_csv(path, ['Product'], [{'Product': 'A', 'Unexpected': 'B'}])


if __name__ == '__main__':
    unittest.main()
