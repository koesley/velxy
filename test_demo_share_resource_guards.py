"""Regression coverage for bounded, public demo share storage."""
import copy
import sqlite3
import time
import unittest

import demo_shares


class DemoShareResourceGuardTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.report = {
            "monthly_rows": [["Month", "Revenue"], ["2026-11", "25.00"]],
            "product_rows": [["Product", "Revenue"], ["Service", "25.00"]],
            "stats": ["Revenue: $25.00"],
            "accepted": 1,
            "rejected": 0,
        }

    def test_valid_share_round_trip(self):
        token = demo_shares.create(self.db, self.report)
        self.assertEqual(demo_shares.get(self.db, token)["monthly_rows"],
                         self.report["monthly_rows"])

    def test_invalid_tokens_never_lookup_or_delete(self):
        token = demo_shares.create(self.db, self.report)
        for value in (None, "", "x", "../" + token, token + "!", "a" * 1000):
            self.assertIsNone(demo_shares.get(self.db, value))
        self.assertIsNotNone(demo_shares.get(self.db, token))

    def test_reject_oversized_row_count(self):
        report = copy.deepcopy(self.report)
        report["product_rows"] = [["x"]] * (demo_shares.MAX_SUMMARY_ROWS + 1)
        with self.assertRaises(ValueError):
            demo_shares.create(self.db, report)

    def test_reject_oversized_cells_and_columns(self):
        for rows in ([[["x" * (demo_shares.MAX_CELL_CHARS + 1)]],
                      [["x"] * (demo_shares.MAX_SUMMARY_COLUMNS + 1)]]):
            report = copy.deepcopy(self.report)
            report["monthly_rows"] = rows
            with self.assertRaises(ValueError):
                demo_shares.create(self.db, report)

    def test_reject_oversized_serialized_csv(self):
        report = copy.deepcopy(self.report)
        report["monthly_rows"] = [["x" * 4000] * 30] * 5
        with self.assertRaises(ValueError):
            demo_shares.create(self.db, report)

    def test_reject_invalid_stats_and_counts(self):
        for stats in (["bad\nline"], ["x"] * 31, ["x" * 8193]):
            report = copy.deepcopy(self.report)
            report["stats"] = stats
            with self.assertRaises(ValueError):
                demo_shares.create(self.db, report)
        for count in (-1, True, "1", 1_000_001):
            report = copy.deepcopy(self.report)
            report["accepted"] = count
            with self.assertRaises(ValueError):
                demo_shares.create(self.db, report)

    def test_failed_validation_does_not_write(self):
        report = copy.deepcopy(self.report)
        report["stats"] = ["invalid\nstat"]
        with self.assertRaises(ValueError):
            demo_shares.create(self.db, report)
        self.assertEqual(self.db.execute(
            "SELECT count(*) FROM sqlite_master WHERE name='demo_shares'"
        ).fetchone()[0], 0)

    def test_expired_share_not_returned(self):
        token = demo_shares.create(self.db, self.report)
        self.db.execute("UPDATE demo_shares SET expires=? WHERE token=?",
                        (int(time.time()) - 1, token))
        self.assertIsNone(demo_shares.get(self.db, token))


if __name__ == "__main__":
    unittest.main()
