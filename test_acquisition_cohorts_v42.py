import datetime as dt
import sqlite3
import unittest
from unittest.mock import patch

import acquisition_cohorts_v42 as cohorts


class AcquisitionCohortTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        self.c.execute("""CREATE TABLE bos59_leads (
            id TEXT, workspace_id TEXT, source TEXT, created INTEGER)""")
        self.c.execute("""CREATE TABLE vx_acquisition_cost35 (
            id TEXT, workspace_id TEXT, source TEXT, amount_cents INTEGER,
            note TEXT, created_by INTEGER, created INTEGER)""")
        self.now = dt.datetime(2026, 7, 15, tzinfo=dt.timezone.utc)

    def tearDown(self):
        self.c.close()

    def ts(self, year, month, day=1):
        return int(dt.datetime(year, month, day, tzinfo=dt.timezone.utc).timestamp())

    def collect(self, workspace="a"):
        with patch("acquisition_cohorts_v42.bos.init"), \
             patch("acquisition_cohorts_v42.acquisition.setup"), \
             patch("acquisition_cohorts_v42.bos.core.access"):
            return cohorts.analyze(self.c, 1, workspace, self.now)

    def test_complete_utc_months_cross_year_and_exclude_current(self):
        rows = cohorts.month_bounds(self.now)
        self.assertEqual([r[0] for r in rows],
                         ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"])
        self.assertEqual(rows[-1][2], self.ts(2026, 7))
        self.assertEqual(rows[0][1], self.ts(2026, 1))
        self.assertEqual(cohorts.month_bounds(dt.datetime(2026, 2, 3, tzinfo=dt.timezone.utc))[0][0],
                         "2025-08")
        with self.assertRaises(ValueError):
            cohorts.month_bounds(dt.datetime(2026, 7, 1))

    def test_workspace_scope_and_date_boundaries(self):
        self.c.executemany("INSERT INTO bos59_leads VALUES (?,?,?,?)", [
            ("one", "a", "Referral", self.ts(2026, 6, 30)),
            ("two", "b", "Referral", self.ts(2026, 6, 30)),
            ("three", "a", "Referral", self.ts(2026, 7, 1)),
            ("four", "a", "Referral", self.ts(2025, 12, 31))])
        self.c.executemany("INSERT INTO vx_acquisition_cost35 VALUES (?,?,?,?,?,?,?)", [
            ("a1", "a", "Referral", 12345, "", 1, self.ts(2026, 6, 30)),
            ("b1", "b", "Referral", 99999, "", 2, self.ts(2026, 6, 30)),
            ("a2", "a", "Referral", 50000, "", 1, self.ts(2026, 7, 1))])
        rows = self.collect()
        self.assertEqual(sum(x["leads"] for x in rows), 1)
        self.assertEqual(sum(x["cost_cents"] for x in rows), 12345)
        self.assertEqual(rows[-1]["sources"][0]["leads"], 1)

    def test_unmatched_sources_and_html_escaping(self):
        self.c.execute("INSERT INTO vx_acquisition_cost35 VALUES (?,?,?,?,?,?,?)",
                       ("x", "a", "<img src=x onerror=alert(1)>", 2500, "", 1, self.ts(2026, 5)))
        with patch("acquisition_cohorts_v42.bos.init"), \
             patch("acquisition_cohorts_v42.acquisition.setup"), \
             patch("acquisition_cohorts_v42.bos.core.access"):
            page = cohorts.render(self.c, 1, "a", self.now)
        self.assertIn("&lt;img", page)
        self.assertNotIn("<img", page)
        self.assertIn("$25.00", page)
        self.assertIn("not a cohort conversion rate", page)
        self.assertIn("New leads: 0", page)

    def test_access_denial_precedes_reads(self):
        with patch("acquisition_cohorts_v42.bos.core.access", side_effect=ValueError("Denied")):
            with self.assertRaisesRegex(ValueError, "Denied"):
                cohorts.analyze(self.c, 1, "b", self.now)

    def test_empty_months_are_explicit(self):
        rows = self.collect()
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(x["leads"] == 0 and x["cost_cents"] == 0 for x in rows))


if __name__ == "__main__":
    unittest.main()
