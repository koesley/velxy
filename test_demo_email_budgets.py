"""Regression tests for anonymous demo email abuse budgets.

Run: python -m unittest -v test_demo_email_budgets
"""
import sqlite3
import unittest
from unittest.mock import patch

import demo_leads


class DemoEmailBudgetsTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        demo_leads.setup(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_normalizes_recipient_before_idempotency(self):
        self.assertTrue(demo_leads.record(self.conn, " A@EXAMPLE.TEST ", "one", now=100000))
        self.assertFalse(demo_leads.record(self.conn, "a@example.test", "one", now=100001))
        self.assertEqual(self.conn.execute("SELECT email FROM demo_leads").fetchone()[0],
                         "a@example.test")

    def test_share_budget_limits_many_distinct_addresses(self):
        with patch.object(demo_leads, "SHARE_DAILY_CAP", 2):
            self.assertTrue(demo_leads.record(self.conn, "a@example.test", "one", now=100000))
            self.assertTrue(demo_leads.record(self.conn, "b@example.test", "one", now=100000))
            self.assertFalse(demo_leads.record(self.conn, "c@example.test", "one", now=100000))
            self.assertTrue(demo_leads.record(self.conn, "c@example.test", "two", now=100000))

    def test_site_budget_limits_many_share_tokens(self):
        with patch.object(demo_leads, "SITE_DAILY_CAP", 2):
            self.assertTrue(demo_leads.record(self.conn, "a@example.test", "one", now=100000))
            self.assertTrue(demo_leads.record(self.conn, "b@example.test", "two", now=100000))
            self.assertFalse(demo_leads.record(self.conn, "c@example.test", "three", now=100000))
            self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM demo_leads").fetchone()[0], 2)

    def test_budgets_roll_off_after_24_hours(self):
        with patch.object(demo_leads, "SITE_DAILY_CAP", 1), patch.object(
                demo_leads, "SHARE_DAILY_CAP", 1):
            self.assertTrue(demo_leads.record(self.conn, "a@example.test", "one", now=100000))
            self.assertFalse(demo_leads.record(self.conn, "b@example.test", "one", now=100001))
            self.assertTrue(demo_leads.record(
                self.conn, "b@example.test", "one", now=100000 + demo_leads.DAY + 1))

    def test_recipient_budget_still_applies(self):
        with patch.object(demo_leads, "SHARE_DAILY_CAP", 100), patch.object(
                demo_leads, "SITE_DAILY_CAP", 100):
            for n in range(demo_leads.DAILY_CAP):
                self.assertTrue(demo_leads.record(
                    self.conn, "a@example.test", "token" + str(n), now=100000))
            self.assertFalse(demo_leads.record(
                self.conn, "a@example.test", "extra", now=100000))

    def test_empty_inputs_do_not_insert(self):
        self.assertFalse(demo_leads.record(self.conn, "", "one", now=100000))
        self.assertFalse(demo_leads.record(self.conn, "a@example.test", "", now=100000))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM demo_leads").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
