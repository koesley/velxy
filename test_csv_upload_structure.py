"""Regression tests for CSV upload structural integrity."""
import csv
import io
import unittest
from unittest.mock import patch

import portal


def payload(rows):
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerows(rows)
    return out.getvalue().encode('utf-8')


class UploadStructureTests(unittest.TestCase):
    def validate(self, data):
        return portal.validate_csv_upload('sales.csv', data)

    def test_normal_csv(self):
        self.assertIn('Order ID', self.validate(payload([portal.REQUIRED, ['1','2026-11-19','Ada','Service','1','10','Paid','East']])))

    def test_quoted_newline_is_one_logical_row(self):
        row = ['1','2026-11-19','Ada\nCustomer','Service','1','10','Paid','East']
        self.assertIn('Ada\nCustomer', self.validate(payload([portal.REQUIRED,row])))

    def test_rejects_extra_columns(self):
        with self.assertRaisesRegex(ValueError, '9 columns'):
            self.validate(payload([portal.REQUIRED, ['1'] * 9]))

    def test_rejects_missing_columns(self):
        with self.assertRaisesRegex(ValueError, '7 columns'):
            self.validate(payload([portal.REQUIRED, ['1'] * 7]))

    def test_rejects_unclosed_quote(self):
        data = payload([portal.REQUIRED]) + b'"unfinished'
        with self.assertRaisesRegex(ValueError, 'Malformed CSV'):
            self.validate(data)

    def test_rejects_more_than_20000_records(self):
        row = ['1'] * len(portal.REQUIRED)
        data = payload([portal.REQUIRED] + [row] * 20001)
        with self.assertRaisesRegex(ValueError, '20,000'):
            self.validate(data)

    def test_accepts_exactly_20000_records(self):
        row = ['1'] * len(portal.REQUIRED)
        self.assertTrue(self.validate(payload([portal.REQUIRED] + [row] * 20000)))

    def test_header_order_still_required(self):
        with self.assertRaisesRegex(ValueError, 'Incorrect columns'):
            self.validate(payload([list(reversed(portal.REQUIRED))]))


if __name__ == '__main__':
    unittest.main()
