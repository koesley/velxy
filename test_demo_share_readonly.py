"""Regression coverage for read-only public demo shares and expiry cleanup."""
import sqlite3
import time
import unittest
from unittest.mock import patch

import demo_shares

REPORT = {
    "monthly_rows": [["Month", "Revenue"], ["2026-11", "12.00"]],
    "product_rows": [["Product", "Revenue"], ["Service", "12.00"]],
    "stats": ["Revenue: 12.00"],
    "accepted": 1, "rejected": 0,
}


class DemoShareReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        demo_shares.setup(self.db)

    def tearDown(self):
        self.db.close()

    def test_valid_share_read_does_not_write(self):
        token = demo_shares.create(self.db, REPORT)
        self.db.set_authorizer(lambda action, *_: sqlite3.SQLITE_DENY
                               if action in (sqlite3.SQLITE_DELETE,
                                             sqlite3.SQLITE_INSERT,
                                             sqlite3.SQLITE_UPDATE)
                               else sqlite3.SQLITE_OK)
        self.assertEqual(demo_shares.get(self.db, token)["accepted"], 1)

    def test_expired_share_invisible_without_deleting(self):
        token = demo_shares.create(self.db, REPORT)
        self.db.execute("UPDATE demo_shares SET expires=? WHERE token=?",
                        (int(time.time()) - 1, token))
        self.db.set_authorizer(lambda action, *_: sqlite3.SQLITE_DENY
                               if action in (sqlite3.SQLITE_DELETE,
                                             sqlite3.SQLITE_INSERT,
                                             sqlite3.SQLITE_UPDATE)
                               else sqlite3.SQLITE_OK)
        self.assertIsNone(demo_shares.get(self.db, token))
        self.assertEqual(self.db.execute(
            "SELECT count(*) FROM demo_shares WHERE token=?", (token,)
        ).fetchone()[0], 1)

    def test_new_share_reclaims_expired_records_only(self):
        old = demo_shares.create(self.db, REPORT)
        live = demo_shares.create(self.db, REPORT)
        self.db.execute("UPDATE demo_shares SET expires=? WHERE token=?",
                        (int(time.time()) - 1, old))
        new = demo_shares.create(self.db, REPORT)
        self.assertIsNone(demo_shares.get(self.db, old))
        self.assertIsNotNone(demo_shares.get(self.db, live))
        self.assertIsNotNone(demo_shares.get(self.db, new))
        self.assertEqual(self.db.execute(
            "SELECT count(*) FROM demo_shares").fetchone()[0], 2)

    def test_expiry_index_created_idempotently(self):
        demo_shares.setup(self.db)
        indexes = self.db.execute("PRAGMA index_list(demo_shares)").fetchall()
        self.assertIn("idx_demo_shares_expires", [row[1] for row in indexes])

    def test_exact_expiration_boundary(self):
        with patch.object(demo_shares.time, "time", return_value=100000):
            token = demo_shares.create(self.db, REPORT)
        expiry = 100000 + demo_shares.SHARE_TTL_DAYS * 86400
        with patch.object(demo_shares.time, "time", return_value=expiry - 1):
            self.assertIsNotNone(demo_shares.get(self.db, token))
        with patch.object(demo_shares.time, "time", return_value=expiry):
            self.assertIsNone(demo_shares.get(self.db, token))


if __name__ == "__main__":
    unittest.main()
